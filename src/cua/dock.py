"""Voice-first dock: the orb pops in where the companion was, with captions and the read-aloud card beside it.

Two frameless windows with no backdrop, so the browser stays visible and usable: the orb window, and a side
panel holding the caption, the typing box and the answer card. Every behaviour goes through dockstate.py.
"""
import ctypes
import os
from dataclasses import replace
from PySide6.QtCore import QPoint, QRect, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QCursor, QFont, QFontMetrics, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget
from .answer_card import AnswerCard
from .config import UserError
from .dockstate import (ACTING, CAPTIONS, CLOSED, DONE, ERROR, IDLE, LISTENING, ORB_LABELS, SPEAKING, THINKING,
                        TYPING, WAITING, DockState)
from .highlighter import Highlighter
from .morph import orb_center, overshoot, panel_rect
from .orb import Orb
from .popup import AnswerWorker
from .browser import window_title
from .rag import APPS, detect_app, detect_platform
from .tts import ReadAloud, intro, spoken

LIGHT = {"surface": "#FFFFFF", "border": "#D5DDDA", "text": "#14231E", "muted": "#46564F", "accent_text": "#0F6E56",
         "active_bg": "#E1F5EE", "active_text": "#085041", "kbd_bg": "#EEF2F1", "kbd_text": "#14231E",
         "focus": "#085041"}
DARK = {"surface": "#1B2321", "border": "#3A4744", "text": "#F1F5F4", "muted": "#B9C7C2", "accent_text": "#5DCAA5",
        "active_bg": "#E1F5EE", "active_text": "#085041", "kbd_bg": "#2C3835", "kbd_text": "#F1F5F4",
        "focus": "#9FE1CB"}


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


class SidePanel(QWidget):
    """Caption, typing box and answer card, placed beside the orb."""
    def __init__(self, dock):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Klicky answer")
        self.dock = dock
        QShortcut(QKeySequence("Escape"), self, activated=dock.escape)

    def keyPressEvent(self, event):
        self.dock.keyPressEvent(event)  # typing anywhere in Klicky switches to the text box


def common_lines():
    """What Klicky says most, in spoken form: every guide step without a {course} blank, each guide's intro, and the
    fixed phrases. The natural voice caches these ahead of time."""
    from .rag import load_corpus
    lines = ["That's it, well done.", "Which course?", "I didn't catch the course. Ask me again when you're ready."]
    for chunk in load_corpus():
        lines.append(intro(chunk))
        lines += [spoken(step) for step in chunk.steps if "{" not in step]
    return lines


class Dock(QWidget):
    def __init__(self, owner):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Klicky")
        self.setObjectName("dock")
        self.owner = owner
        self.machine = DockState(self.on_state)
        self.context_app = self.return_hwnd = self.context_platform = None
        self.listener = self.monitor = self.worker = None
        self.answer, self.colors, self.answered = None, LIGHT, False
        self.walk, self.pointed_rect = None, None
        self.probe_factory = None  # tests inject a fake control lookup for walkthroughs
        self.choice, self.last_question, self.choice_misses = None, "", 0  # "Which course?" waiting for an answer
        self.page_courses = self.page_find = self.page_seer = None  # tests inject fakes; None means the real page and model
        self.page_worker = None
        self.action_factory = None  # tests inject a fake action runner
        self.actor = None
        self.asked_by_voice = False
        self.auto_close = QTimer(self)
        self.auto_close.setSingleShot(True)
        self.auto_close.timeout.connect(lambda: self.state == DONE and self.answer is None and self.close_dock())
        self.voice_factory = self.monitor_factory = self.answer_factory = None  # tests inject fakes here
        self.tts = ReadAloud()
        self.highlighter = Highlighter(self.guide_companion)
        self.anchor = QPoint()
        self.on_closed = lambda: None
        self.panel = SidePanel(self)
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.card = AnswerCard()
        self.card.hide()
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
        layout.addWidget(self.caption)
        layout.addWidget(self.input)
        layout.addWidget(self.card)
        # No trailing stretch: the panel is sized to its contents, and a stretch would take the height the card
        # asked for (height-for-width), leaving wrapped steps cut off at their one-line size.
        self.orb = Orb()
        self.orb.clicked.connect(self.orb_clicked)
        orb_layout = QVBoxLayout(self)
        orb_layout.setContentsMargins(0, 0, 0, 0)
        orb_layout.addWidget(self.orb)
        QShortcut(QKeySequence("Escape"), self, activated=self.escape)
        self.pop = QVariantAnimation(self)
        self.pop.valueChanged.connect(self.set_pop)
        self.pop.finished.connect(self.pop_finished)
        self.closing = False
        # Click anywhere outside Klicky closes it; polled, so no system-wide mouse hook is needed.
        self.outside = QTimer(self)
        self.outside.setInterval(50)
        self.outside.timeout.connect(self.check_outside_click)
        self.button_was_down = False

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
    def open_for(self, app, hwnd, listen=True, anchor=None):
        """anchor: where the orb's centre should be (the companion's spot); defaults to the pointer."""
        if self.state == CLOSED:
            self.context_app, self.return_hwnd = app, hwnd
            self.context_platform = self.platform_of(hwnd)
            self.highlighter.cache.clear()
            self.answer = None
            self.card.hide()
            self.restyle()
            self.machine.fire("open")
            area = self.screen_area(anchor or QCursor.pos())
            self.anchor = orb_center(anchor or QCursor.pos(), area, self.orb.diameter // 2)
            self.closing = False
            self.pop.stop()
            self.setWindowOpacity(1.0)
            self.panel.setWindowOpacity(1.0)
            self.reposition()
            self.show()
            self.orb.start()
            self.animate_pop(.5, 1.0, 220, overshoot())  # pops in with a small overshoot
            self.button_was_down = True  # ignore the click that may have opened Klicky
            self.outside.start()
        elif hwnd:
            self.context_app, self.return_hwnd = app, hwnd
            self.context_platform = self.platform_of(hwnd)
        self.raise_()
        self.activateWindow()
        self.orb.setFocus()
        self.reposition()
        if listen:
            self.listen_now()

    @staticmethod
    def platform_of(hwnd):
        """The site the hotkey was pressed on (e.g. the LMS), from the browser's title, so its guides rank first."""
        try:
            return detect_platform(title=window_title(hwnd))
        except Exception:
            return None

    def screen_area(self, point):
        screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def animate_pop(self, start, end, ms, curve=None):
        if self.orb.reduced:
            self.set_pop(end)
            self.pop_finished()
            return
        self.pop.stop()
        self.pop.setDuration(ms)
        self.pop.setStartValue(start)
        self.pop.setEndValue(end)
        if curve is not None:
            self.pop.setEasingCurve(curve)
        self.pop.start()

    def set_pop(self, value):
        self.orb.pop = value
        self.orb.update()
        if self.closing:  # scale down and fade together
            fade = max(0.0, (value - .6) / .4)
            self.setWindowOpacity(fade)
            self.panel.setWindowOpacity(fade)

    def pop_finished(self):
        if self.closing:
            self.closing = False
            self.hide()
            self.panel.hide()
            self.orb.pop = 1.0
            self.on_closed()

    def check_outside_click(self):
        if os.name != "nt" or not self.isVisible():
            return
        down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        if down and not self.button_was_down:
            pos = QCursor.pos()
            inside = self.frameGeometry().contains(pos) or self.panel.isVisible() and self.panel.frameGeometry().contains(pos)
            if self.walk and self.walk.active:
                self.walk.clicked(pos)
            elif not inside:
                self.close_dock()
        self.button_was_down = down

    def restyle(self):
        p = self.owner.profile
        self.highlighter.label_rings = not self.settings.companion
        px = max(16, self.settings.font_px)
        cap = max(18, px + 2)
        self.colors = c = palette(p.key)
        self.orb.set_diameter(72 if p.key == "low_vision" else 56)
        self.orb.focus_color = c["focus"]
        self.card.reduced = self.orb.reduced
        font = QFont("Segoe UI")
        font.setPixelSize(cap)
        self.caption.setFont(font)
        self.panel.setFixedWidth(self.panel_width())
        self.setStyleSheet("* { background:transparent; }")
        self.panel.setStyleSheet(
            f'* {{ background:transparent; color:{c["text"]}; font-family:"Segoe UI"; font-size:{px}px; }}'
            f' #card {{ background:{c["surface"]}; border:1px solid {c["border"]}; border-radius:12px; }}'
            f' #cardTitle {{ font-weight:500; font-size:{px + 2}px; }}'
            f' QLabel#step {{ padding:6px 8px; border-radius:8px; }}'
            f' QLabel#step[active="true"] {{ background:{c["active_bg"]}; color:{c["active_text"]}; }}'
            f' #note {{ color:{c["muted"]}; font-size:{max(16, px - 2)}px; }}'
            f' QLabel#caption {{ background:{c["surface"]}; border:1px solid {c["border"]}; border-radius:10px; padding:6px 14px; font-size:{cap}px; }}'
            f' QLineEdit#typed {{ background:{c["surface"]}; border:2px solid {c["border"]}; border-radius:10px; padding:8px 12px; font-size:{cap}px; }}'
            f' QLineEdit#typed:focus {{ border:3px solid {c["focus"]}; }}')
        if self.answer:
            self.card.colors = c
            self.card.render()

    def panel_width(self):
        return max(320, self.settings.font_px * 17)  # about 320 px; wider for large text

    def caption_width(self):
        return self.panel_width() - 30

    def reposition(self):
        """Orb centred on its anchor; panel beside it. Neither follows the mouse while open."""
        if self.state == CLOSED:
            return
        self.adjustSize()
        self.move(self.anchor.x() - self.width() // 2, self.anchor.y() - self.height() // 2)
        has_content = not self.caption.isHidden() or not self.input.isHidden() or not self.card.isHidden()
        if not has_content:
            self.panel.hide()
            return
        # Wrapped captions and steps need height-for-width; adjustSize alone under-measures them.
        layout = self.panel.layout()
        layout.activate()
        width = self.panel_width()
        height = layout.totalHeightForWidth(width) if layout.hasHeightForWidth() else layout.totalSizeHint().height()
        height = max(height, layout.totalMinimumSize().height())
        self.panel.setFixedHeight(height)
        self.panel.setGeometry(panel_rect(self.anchor, width, height, self.screen_area(self.anchor)))
        if not self.closing:
            self.panel.show()
            self.panel.raise_()

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
        elif self.state in (IDLE, DONE, ERROR, TYPING, WAITING):
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
        if self.choice:
            self.set_caption(f"“{text}”")
            self.answer_choice(text)
            return
        self.set_caption(f"“{text}”  Finding the answer...")
        self.asked_by_voice = True
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
        self.reposition()
        self.panel.activateWindow()
        self.input.setFocus()
        self.input.end(False)
        QTimer.singleShot(0, self.reposition)

    def submit_typed(self):
        text = self.input.text().strip()
        if not text or self.state != TYPING:
            return
        if self.choice:  # the answer to "Which course?", not a new question
            self.machine.fire("submit")
            self.answer_choice(text)
            return
        try:
            from .planning import route
            route(text, self.settings.engine)
        except UserError as exc:
            self.set_caption(str(exc))
            return
        self.machine.fire("submit")
        self.asked_by_voice = False
        self.route(text, spoken_question=False)

    # ---- answering -----------------------------------------------------------------------------------------
    def route(self, text, spoken_question):
        from .planning import HELP_START, parse_action, parse_task
        action = parse_action(text) if self.settings.actions and self.return_hwnd and not HELP_START.match(text) else None
        if action:
            self.act(action.action)
            return
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
        self.last_question, self.choice = question, None
        # A browser named in the question wins; otherwise answer for the browser the hotkey was pressed in.
        if self.context_app and settings.rag_app == "auto" and detect_app(question) is None:
            settings = replace(settings, rag_app=self.context_app)
        self.answered = False
        self.worker = AnswerWorker(settings, question, self.answer_factory, self.context_platform)
        self.worker.answered.connect(self.on_answer)
        self.worker.status.connect(lambda state, message: self.on_fail(message) if state == "error" and not self.answered else None)
        self.worker.start()

    # ---- doing it for the person -----------------------------------------------------------------------
    def act(self, action):
        """Do one allowed browser action: the companion flies to the button and Klicky presses it."""
        from .browser_actions import SPECS, ActionWorker
        if not self.machine.fire("act"):
            return
        self.answer = None
        self.card.hide()
        self.set_caption(SPECS[action]["doing"] + "...")
        factory = self.action_factory or ActionWorker
        self.actor = factory(self.return_hwnd, action, self.context_app)
        self.actor.located.connect(self.on_action_located)
        self.actor.pressing.connect(self.on_action_pressing)
        self.actor.done.connect(self.on_action_done)
        self.actor.failed.connect(self.on_fail)
        self.actor.start()

    def on_action_located(self, rect):
        if rect is None or self.state != ACTING:
            return
        from .highlighter import to_logical
        logical = to_logical(rect)
        overlay = getattr(self.highlighter, "overlay", None)
        if overlay is not None:
            overlay.show_ring(logical, "")
        self.guide_companion(logical)

    def on_action_pressing(self):
        companion = getattr(self.owner, "companion", None)
        if companion is not None and self.state == ACTING:
            companion.press()

    def on_action_done(self, message):
        if self.state != ACTING:
            return
        self.machine.fire("acted")
        self.set_caption(message)
        if self.settings.read_aloud or self.asked_by_voice:
            self.speak([message])
        QTimer.singleShot(900, self.quiet)  # the ring and the companion stay a moment on what was pressed
        self.auto_close.start(4000)        # then Klicky gets out of the way

    def on_answer(self, answer):
        if self.state != THINKING:
            return
        self.answered = True
        self.answer = answer
        if answer.ask and answer.grounded and self.return_hwnd and self.context_platform in answer.apps:
            self.start_choice(answer)  # on the LMS page itself: ask which course, then guide inside the page
            return
        self.card.show_answer(answer, self.colors)
        self.card.show()
        if self.points_at_browser():
            self.highlighter.prefetch(self.card.visible_steps, self.return_hwnd)  # pointing is instant when each step is read
        announce(self, answer.spoken() if answer.grounded else answer.note)
        read = self.settings.read_aloud and not (self.settings.screen_reader_quiet and screen_reader_running())
        from .walkthrough import Walkthrough, actionable_steps
        steps = self.card.visible_steps
        # Only guides that declare a sequence become walkthroughs; alternatives in a list are read as usual.
        actionable = min(answer.walk, actionable_steps(steps)) if answer.grounded and self.return_hwnd and self.points_at_browser() else 0
        if read and actionable >= 2 and self.machine.fire("answer_read"):
            # Several steps that each need the person to act: guide them one at a time and wait.
            self.walk = Walkthrough(self, steps, actionable, self.return_hwnd, self.probe_factory)
            self.walk.start()
        elif read and self.machine.fire("answer_read"):
            self.read_answer()
        else:
            self.machine.fire("answer_quiet")
            self.point_at_first_step()
        self.orb.setFocus()

    # ---- guided steps inside the page: "Which course?" then point at each link ----------------------------
    def reading(self):
        return self.settings.read_aloud and not (self.settings.screen_reader_quiet and screen_reader_running())

    def start_choice(self, answer):
        from . import page
        self.set_caption("Checking your courses...")
        self.page_worker = page.PageWorker(self.page_courses or page.courses, self.return_hwnd)
        self.page_worker.result.connect(lambda names, answer=answer: self.on_courses(answer, names or []))
        self.page_worker.start()

    def on_courses(self, answer, names):
        from .page import MAX_OPTIONS, pick, short_name
        if self.state != THINKING or self.answer is not answer:
            return
        full = {}
        for name in names:
            full.setdefault(short_name(name), name)
        options = list(full)[:MAX_OPTIONS]
        if not options:  # couldn't read the courses: give the steps as written
            self.show_plain(answer)
            return
        chosen = pick(self.last_question, options, numbers=False)  # "how do I submit my HCI assignment" names it already
        if chosen:
            self.begin_guide(answer, chosen, full[chosen])
            return
        current = next((name for name in names if name in self.page_title()), None)  # the course you're in, if any
        if current:  # inside a course and none named: that's the one (ask only from Home)
            self.begin_guide(answer, short_name(current), current, lead=f"You're in {short_name(current)}, so I'll use it.")
            return
        self.choice, self.choice_misses = (answer, options, full, current), 0
        self.card.show_choice("Which course?", options, self.colors)
        self.card.show()
        question = (f"Which course? {', '.join(options[:-1])}, or {options[-1]}." if 1 < len(options) <= MAX_OPTIONS
                    else f"Which course? Say its name, for example {options[0]}.")
        self.ask_choice(question)

    def ask_choice(self, question):
        announce(self, question)
        self.reposition()
        if self.reading() and self.machine.fire("answer_read"):
            self.speak([question], on_end=self.listen_for_choice)
        else:
            self.machine.fire("answer_quiet")
            self.set_caption(question)

    def listen_for_choice(self):
        if self.state == SPEAKING and self.choice:
            self.machine.fire("finished")
            self.start_listening()

    def answer_choice(self, text):
        from .page import THIS_ONE, pick, short_name
        answer, options, full, current = self.choice
        chosen = pick(text, options)
        if not chosen and current and THIS_ONE.search(text):  # "this one" while inside a course
            chosen = short_name(current)
            full = {**full, chosen: current}
        if chosen:
            self.choice = None
            self.begin_guide(answer, chosen, full[chosen])
            return
        self.choice_misses += 1
        if self.choice_misses >= 2:
            self.choice = None
            self.machine.fire("fail")
            self.set_caption("I didn't catch the course. Ask me again when you're ready.")
            return
        self.ask_choice(f"Sorry, which course? Say its name, for example {options[0]}.")

    def begin_guide(self, answer, short, full, lead=None):
        from .assistant import fill
        from .pagewalk import PageWalkthrough
        steps = fill(answer.template, answer.ask, short)
        self.answer = guided = replace(answer, steps=steps)
        self.card.show_answer(guided, self.colors)
        self.card.show()
        here = full in self.page_title()  # e.g. "Sakai : Computer Security (Class No ...) : Overview"
        start = 1 if here and answer.points[:1] == ("course",) else 0
        lead = lead or f"Okay, {short}." + (f" You're already in {short}." if start else "")
        if not (self.reading() and self.machine.fire("answer_read")):
            self.machine.fire("answer_quiet")
            announce(self, guided.spoken())
            return
        self.walk = PageWalkthrough(self, steps, answer.points, self.return_hwnd, full, start, lead, finder=self.page_find,
                                    seer=self.page_seer or self.vision_seer())
        self.walk.start()

    def vision_seer(self):
        """The screenshot fallback for guided page steps, or None when vision is off or no backend is available."""
        from . import vision
        from .keys import load_keys
        load_keys()  # a key saved in keys.env while Klicky runs counts from the next walkthrough on
        settings = self.settings
        if vision.backend(settings) is None:
            return None
        return lambda hwnd, spec, chosen, step: vision.see(hwnd, spec, chosen, step, settings)

    def page_title(self):
        try:
            return window_title(self.return_hwnd) or ""
        except Exception:
            return ""

    def show_plain(self, answer):
        """The steps as written, read aloud, without pointing (the page couldn't be read)."""
        self.card.show_answer(answer, self.colors)
        self.card.show()
        announce(self, answer.spoken())
        if self.reading() and self.machine.fire("answer_read"):
            self.read_answer()
        else:
            self.machine.fire("answer_quiet")

    def lines(self):
        if not self.answer.grounded:
            return [self.answer.note]
        return [intro(self.answer)] + [spoken(step) for step in self.card.visible_steps]

    def warm_voice(self):
        """At start-up: begin caching the natural voice's common lines, so the first answer already sounds quick."""
        if self.settings.voice_engine == "natural" and type(self.tts) is ReadAloud:
            try:
                self.reader()
            except Exception:
                pass

    def reader(self):
        """The voice to read with, switched when the setting changes. The Windows voice stays as the fallback."""
        from .neural_tts import NeuralReadAloud
        natural = self.settings.voice_engine == "natural"
        if natural and type(self.tts) is ReadAloud:
            self.tts = NeuralReadAloud(fallback=self.tts)
            self.tts.neural_voice = self.settings.neural_voice
            self.tts.prewarm(common_lines(), self.settings.speech_rate)
        elif not natural and isinstance(self.tts, NeuralReadAloud):
            neural, self.tts = self.tts, self.tts.fallback
            neural.stop()
            neural.closed = True
        self.tts.voice_name = self.settings.tts_voice
        if isinstance(self.tts, NeuralReadAloud):
            self.tts.neural_voice = self.settings.neural_voice
        return self.tts

    def speak(self, lines, on_line_start=None, on_end=None):
        self.reader().speak(lines, self.settings.speech_rate, on_line_start=on_line_start, on_end=on_end)

    def read_answer(self):
        self.reader().speak(self.lines(), self.settings.speech_rate, on_line_start=self.on_line, on_end=self.on_read_end)
        self.start_monitor()

    def on_line(self, index):
        step = index - 1  # line 0 is the spoken intro
        self.card.set_active(step)
        steps = self.card.visible_steps
        if 0 <= step < len(steps) and self.points_at_browser():
            self.highlighter.point(steps[step], self.return_hwnd)

    def on_read_end(self):
        self.stop_monitor()
        self.card.set_active(-1)
        self.walk = None
        self.machine.fire("finished")

    def guide_companion(self, rect):
        """The companion flies out of the orb to the control being explained, or stops pointing."""
        self.pointed_rect = rect
        if rect is not None and self.state != CLOSED:
            self.move_out_of_the_way(rect)
        companion = getattr(self.owner, "companion", None)
        if companion is None:
            return
        if rect is None or not self.settings.companion or self.state == CLOSED:
            companion.stop_guide()
            return
        if getattr(self.highlighter, "current_target", None) == "zoom" and getattr(self.highlighter, "current_kind", "control") != "row":
            # The zoom row is minus, percentage, plus: point at the plus at its right end.
            tip = QPoint(rect.right() - rect.height() // 2, rect.bottom() - 4)
        else:
            # Tip rests on the lower middle of the control so its icon stays visible above the pointer.
            tip = QPoint(rect.center().x(), rect.bottom() - 4)
        companion.guide(self.anchor, tip)

    def move_out_of_the_way(self, rect):
        """Klicky must never cover the control it asks the person to click (menus open at the top right)."""
        target = rect.adjusted(-12, -12, 12, 12)
        if not (self.frameGeometry().intersects(target) or self.panel.isVisible() and self.panel.frameGeometry().intersects(target)):
            return
        area = self.screen_area(rect.center())
        # Below and to the left of the control, with the card to the orb's left or right as space allows.
        wanted = QPoint(rect.left() - self.panel_width() - 70, rect.bottom() + 90)
        self.anchor = orb_center(wanted, area, self.orb.diameter // 2)
        self.reposition()

    def points_at_browser(self):
        """Only browser guides point at controls: the pointer finds the browser's own buttons, not a site's page,
        and words like "star" or "Back" in a site's guide would otherwise land on the browser's buttons."""
        return bool(self.answer and any(app in APPS for app in self.answer.apps))

    def point_at_first_step(self):
        if not self.points_at_browser():
            return
        for step in self.card.visible_steps:
            from .highlighter import target_for
            if target_for(step):
                self.highlighter.point(step, self.return_hwnd)
                return

    def stop_reading(self):
        self.quiet()
        self.machine.fire("stop")

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
        if self.state != SPEAKING or self.walk:
            return
        self.quiet()
        if self.machine.fire("barge_in"):
            self.listen(cue=False)  # the person is already talking; no beep over their words

    def quiet(self):
        """Stop reading, stop guiding or listening for barge-in, and clear highlights."""
        if self.walk:
            self.walk.stop()
            self.walk = None
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
        elif self.state in (SPEAKING, WAITING):
            self.stop_reading()

    def escape(self):
        if self.state in (LISTENING, THINKING, ACTING):
            self.stop_listener()
            if self.worker and self.worker.isRunning():
                self.worker.stop_event.set()
            if self.actor and self.actor.isRunning():
                self.actor.stop_event.set()
            self.machine.fire("cancel")
        elif self.state in (SPEAKING, WAITING):
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
        if self.state in (LISTENING, THINKING, ACTING):
            self.machine.fire("cancel")
        elif self.state != CLOSED:
            self.machine.fire("close")

    def finish_close(self):
        self.choice = None
        self.stop_listener()
        if self.worker and self.worker.isRunning():
            self.worker.stop_event.set()
        self.quiet()
        self.outside.stop()
        self.orb.stop()  # stops the animation loop; the microphone closes when the listener thread ends
        self.closing = True
        self.animate_pop(1.0, .6, 180)  # orb and card shrink and fade, then the companion returns
        hwnd, self.return_hwnd = self.return_hwnd, None
        if hwnd:
            try:
                ctypes.windll.user32.SetForegroundWindow(hwnd)  # focus goes back where it was
            except (AttributeError, OSError):
                pass
