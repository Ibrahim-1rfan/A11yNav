"""Voice-first dock: state machine, read-aloud text, orb motion, pointing and the full flow with fake audio.

Real Qt widgets and real guide retrieval; the microphone, speech output and barge-in monitor are fakes, so
the suite never opens the microphone or makes a sound.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import threading
import time
from types import SimpleNamespace
import pytest
from PySide6.QtCore import QEvent, Qt, QThread, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QApplication, QLabel
from cua.answer_card import AnswerCard, rich_step, VISIBLE_STEPS
from cua.assistant import Answer, build_assistant
from cua.config import Settings
from cua.dock import LIGHT, last_two_lines
from cua.dockstate import CLOSED, DONE, ERROR, IDLE, LISTENING, SPEAKING, THINKING, TYPING, WAITING, DockState
from cua.highlighter import target_for
from cua.orb import Orb
from cua.tts import intro, sapi_rate, spoken
from cua.voice import BargeInMonitor, NO_MIC


# ---- pure logic -----------------------------------------------------------------------------------------
def test_state_machine_follows_the_spec_and_ignores_stray_events():
    seen = []
    machine = DockState(lambda old, new, event: seen.append((old, new)))
    assert machine.fire("heard") is None and machine.state == CLOSED  # a late result cannot jump the dock
    for event, state in [("open", IDLE), ("start", LISTENING), ("heard", THINKING), ("answer_read", SPEAKING),
                         ("barge_in", LISTENING), ("heard", THINKING), ("answer_read", SPEAKING), ("stop", DONE),
                         ("type", TYPING), ("submit", THINKING),
                         ("answer_quiet", DONE), ("start", LISTENING), ("fail", ERROR), ("start", LISTENING),
                         ("cancel", CLOSED)]:
        assert machine.fire(event) == state, event
    assert machine.fire("answer_read") is None and machine.fire("replay") is None
    assert len(seen) == 15


@pytest.mark.parametrize("step,expected", [
    ("To zoom in, press Ctrl and Plus (+) together.", "To zoom in, press Control and Plus together."),
    ("Press Ctrl, Shift and T.", "Press Control, Shift and T."),
    ("Full screen on or off: F11.", "Full screen on or off: F 11."),
    ("Press Esc to close it ✅ **now**", "Press Escape to close it now"),
])
def test_spoken_version_has_no_symbols_or_abbreviations(step, expected):
    assert spoken(step) == expected


def test_intro_rate_and_key_chips():
    assert intro(Answer("Make pages bigger (zoom)", (), (), (), True, task="make pages and text bigger")) == "Here's how to make pages and text bigger."
    assert intro(Answer("Make pages bigger (zoom)", (), (), (), True)) == "Here's help with make pages bigger."
    assert sapi_rate(1.0) == 0 and sapi_rate(.8) == -2 and sapi_rate(1.2) == 2
    html = rich_step("Press Ctrl and Plus (+) together, then Ctrl and 0.", LIGHT)
    assert html.count("Consolas") == 4 and "&nbsp;+&nbsp;" in html and "&nbsp;0&nbsp;" in html
    assert "<script>" not in rich_step("<script>x</script>", LIGHT)


def test_barge_in_ignores_klickys_own_echo_but_hears_the_person():
    monitor = BargeInMonitor()
    echo = [.04, .05, .03, .06, .05, .04, .05, .03, .05, .04, .06, .05]  # 600 ms of Klicky's voice in the mic
    assert not monitor.decide(echo + [.07] * 20)                           # louder words in the answer
    assert not monitor.decide(echo + [.3, .3, .02, .3, .3, .02])          # short bumps, not held for 300 ms
    assert monitor.decide(echo + [.25] * 6)                                # the person talking over it


def test_pointer_targets_and_caption_truncation():
    assert target_for("With the mouse, select More (the three dots at the top right).") == "menu"
    assert target_for("Open Settings and more (three dots, top right), then Settings.") == "menu"
    assert target_for("Open the menu (three lines at the top right) and choose Settings.") == "menu"
    assert target_for("You can also select Reading mode in the address bar.") in {"reader", "address"}
    assert target_for("Press Ctrl and F to open the find bar.") is None
    app = QApplication.instance() or QApplication([])
    font = QFont("Segoe UI")
    font.setPixelSize(18)
    long = " ".join(f"word{i}" for i in range(80))
    short = last_two_lines(long, font, 300)
    assert short.startswith("… ") and short.endswith("word79") and len(short) < len(long)


def test_orb_follows_the_voice_breathes_and_respects_reduced_motion():
    app = QApplication.instance() or QApplication([])
    orb = Orb()
    orb.reduced = False
    orb.set_mode("listening", "Stop listening")
    assert orb.accessibleName() == "Stop listening"
    orb.set_level(.1)  # x6 -> 0.6 target
    for _ in range(30):
        orb.tick()
    assert orb.level == pytest.approx(.6, abs=.01)
    assert orb.scales[2] > orb.scales[1] > orb.scales[0] > 1
    loud = orb.scales
    orb.set_mode("speaking", "Stop reading")
    peaks = []
    for i in range(200):
        orb.started -= .016
        orb.tick()
        peaks.append(orb.scales[2])
    assert max(peaks) < 1.26 and max(peaks) < loud[2]  # speaking pulses less than a loud voice
    orb.set_mode("thinking", "Finding the answer")
    orb.started -= 1.4  # half of the 2.8 s breath
    orb.tick()
    assert orb.scales[0] == pytest.approx(1.05, abs=.002) and orb.scales[2] == pytest.approx(1.3, abs=.01)
    still = Orb()
    still.reduced = True
    still.start()
    assert not still.timer.isActive()  # no scaling or pulsing at all


def test_card_shows_at_most_three_steps_and_no_buttons():
    from PySide6.QtWidgets import QPushButton
    app = QApplication.instance() or QApplication([])
    card = AnswerCard()
    answer = Answer("Make pages bigger (zoom)", ("edge",), tuple(f"Step {i} text." for i in range(5)), ("https://support.microsoft.com/x",), True)
    card.show_answer(answer, LIGHT)
    assert len(card.step_labels) == VISIBLE_STEPS == 3 and card.title.text() == "Make pages bigger"
    assert card.findChildren(QPushButton) == [] and not card.note.isVisibleTo(card)
    card.set_active(1)
    assert card.step_labels[1].property("active") == "true" and card.step_labels[0].property("active") == "false"


# ---- the dock end to end, with fakes -------------------------------------------------------------------
class FakeTTS:
    def __init__(self):
        self.calls, self.stops, self.voice_name, self.volume = [], 0, "", 100
    def speak(self, lines, rate=1.0, on_line_start=None, on_end=None):
        self.calls.append(SimpleNamespace(lines=lines, rate=rate, line=on_line_start, end=on_end))
    def stop(self):
        self.stops += 1
    def close(self):
        pass


class FakeListener(QThread):
    level, stage, partial, heard, failed = Signal(float), Signal(str), Signal(str), Signal(str), Signal(str)
    def __init__(self, text=None, wait=False, fail=None):
        super().__init__()
        self.stop_event, self.text, self.wait_for_stop, self.fail = threading.Event(), text, wait, fail
    def run(self):
        self.stage.emit("listening")
        self.level.emit(.08)
        if self.fail:
            self.failed.emit(self.fail)
            return
        if self.wait_for_stop:
            self.stop_event.wait(3)
            self.stage.emit("stopped")
            return
        self.partial.emit(" ".join(self.text.split()[:3]))
        time.sleep(.05)
        self.stage.emit("transcribing")
        self.heard.emit(self.text)


class FakeMonitor(QThread):
    barged = Signal()
    def __init__(self):
        super().__init__()
        self.stop_event = threading.Event()
    def run(self):
        self.stop_event.wait(5)


def wait_for(app, condition, seconds=4):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.01)
    return condition()


@pytest.fixture
def dock_setup(monkeypatch):
    from cua.ui import MainWindow
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("cua.dock.screen_reader_running", lambda: False)
    window = MainWindow(Settings(hotkey=""))
    dock = window.dock
    dock.tts = FakeTTS()
    dock.silent = dock.tts  # typed questions are answered in text alone; the flow is the same
    listeners, monitors, captions, focused = [], [], [], []
    dock.voice_factory = lambda: listeners[-1] if listeners and not listeners[-1].isRunning() and not listeners[-1].isFinished() else listeners.append(FakeListener("how do I make the text bigger in firefox")) or listeners[-1]
    dock.monitor_factory = lambda: monitors.append(FakeMonitor()) or monitors[-1]
    dock.answer_factory = lambda: build_assistant(Settings())
    pointed = []
    dock.highlighter = SimpleNamespace(point=lambda step, hwnd: pointed.append((step, hwnd)), clear=lambda: pointed.append(None), cache={},
                                       prefetch=lambda steps, hwnd: None)
    original = dock.set_caption
    monkeypatch.setattr(dock, "set_caption", lambda text, whole=False: (captions.append(text), original(text, whole)))
    monkeypatch.setattr("cua.dock.ctypes.windll.user32.SetForegroundWindow", focused.append)
    monkeypatch.setattr("cua.ui.foreground_app", lambda: (12345, "chrome"))
    yield SimpleNamespace(app=app, window=window, dock=dock, listeners=listeners, monitors=monitors, captions=captions,
                          focused=focused, pointed=pointed)
    dock.close_dock()
    window.close()


def test_hotkey_listens_captions_thinks_and_reads_each_step(dock_setup):
    s = dock_setup
    s.window.summon()
    dock = s.dock
    assert dock.isVisible() and not s.window.isVisible()           # only the small dock opens
    assert wait_for(s.app, lambda: dock.state == SPEAKING)
    assert "how do I" in s.captions                                # live caption while speaking
    assert "Got it, finding the answer..." in s.captions           # thinking, triggered by end of speech
    call = dock.tts.calls[-1]
    assert call.lines[0] == "Here's how to make pages and text bigger."
    assert "Control" in call.lines[1] and "Plus" in call.lines[1] and "+" not in call.lines[1] and "Ctrl" not in call.lines[1]
    assert len(dock.card.step_labels) <= 3 and len(call.lines) == len(dock.card.step_labels) + 1
    assert dock.answer.apps == ("firefox",)                       # a browser named in the question wins
    assert dock.orb.accessibleName() == "Stop reading" and s.monitors and s.monitors[-1].isRunning()  # barge-in armed
    call.line(1)
    assert dock.card.step_labels[0].property("active") == "true"
    call.line(2)
    assert dock.card.step_labels[1].property("active") == "true" and dock.card.step_labels[0].property("active") == "false"
    call.end()
    assert dock.state == DONE and s.monitors[-1].stop_event.is_set()
    dock.escape()
    assert dock.state == CLOSED and s.focused == [12345]
    assert wait_for(s.app, lambda: not dock.isVisible() and not dock.panel.isVisible())  # 180 ms shrink and fade


def test_talking_over_the_answer_stops_reading_and_listens_again(dock_setup):
    s = dock_setup
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.state == SPEAKING)
    stops = s.dock.tts.stops
    s.listeners.append(FakeListener(wait=True))
    s.monitors[-1].barged.emit()
    assert s.dock.state == LISTENING and s.dock.tts.stops > stops and s.dock.card.isHidden()
    assert wait_for(s.app, lambda: s.listeners[-1].isRunning())
    s.dock.escape()                                                # Esc while listening cancels and closes
    assert s.dock.state == CLOSED and wait_for(s.app, lambda: not s.listeners[-1].isRunning())


def test_orb_click_and_escape_stop_reading(dock_setup):
    s = dock_setup
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.state == SPEAKING)
    assert s.dock.tts.calls[-1].rate == pytest.approx(1.0)        # speed comes from Settings
    s.dock.orb.click()
    assert s.dock.state == DONE and s.dock.isVisible()             # stopped, answer stays visible
    s.dock.orb.click()
    assert wait_for(s.app, lambda: s.dock.state in (LISTENING, THINKING, SPEAKING))  # orb asks again
    assert wait_for(s.app, lambda: s.dock.state == SPEAKING)
    s.dock.escape()
    assert s.dock.state == DONE and s.dock.isVisible()             # first Esc stops speech
    s.dock.escape()
    assert s.dock.state == CLOSED


def test_typing_takes_over_from_listening(dock_setup):
    s = dock_setup
    s.listeners.append(FakeListener(wait=True))
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.state == LISTENING and s.listeners[-1].isRunning())
    s.dock.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_H, Qt.KeyboardModifier.NoModifier, "h"))
    assert s.dock.state == TYPING and s.dock.input.text() == "h" and s.listeners[-1].stop_event.is_set()
    s.dock.input.setText("how do I turn on dark mode")
    s.dock.submit_typed()
    assert wait_for(s.app, lambda: s.dock.state == SPEAKING)
    assert "dark mode" in s.dock.tts.calls[-1].lines[0].lower()


def test_read_aloud_off_or_screen_reader_leaves_the_answer_quiet(dock_setup, monkeypatch):
    s = dock_setup
    s.window.settings = Settings(hotkey="", read_aloud=False)
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.state == DONE) and s.dock.tts.calls == [] and s.dock.card.isVisible()
    s.dock.close_dock()
    s.window.settings = Settings(hotkey="")
    monkeypatch.setattr("cua.dock.screen_reader_running", lambda: True)
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.state == DONE) and s.dock.tts.calls == []


def test_microphone_problems_are_never_a_dead_end(dock_setup):
    s = dock_setup
    s.listeners.append(FakeListener(fail=NO_MIC))
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.state == TYPING)
    assert s.dock.input.isVisible() and "Type your question instead" in s.captions[-1]
    s.dock.close_dock()
    s.listeners.append(FakeListener(fail="Couldn't hear that. Tap the orb to try again, or start typing."))
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.state == ERROR) and s.dock.orb.accessibleName() == "Try again"
    s.dock.orb.click()
    assert wait_for(s.app, lambda: s.dock.state in (LISTENING, THINKING, SPEAKING))


def test_spoken_search_hands_over_to_the_search_agent(dock_setup, monkeypatch):
    s = dock_setup
    searches = []
    monkeypatch.setattr(s.window, "run_search", searches.append)
    s.listeners.append(FakeListener("search for accessible computer interfaces"))
    s.window.summon()
    assert wait_for(s.app, lambda: searches == ["search for accessible computer interfaces"])
    assert s.dock.state == CLOSED and wait_for(s.app, lambda: not s.dock.isVisible())


def test_text_sizes_meet_the_minimums(dock_setup):
    s = dock_setup
    s.window.summon()
    style = s.dock.panel.styleSheet()
    assert "font-size:18px" in style and s.dock.caption.font().pixelSize() >= 18
    assert s.dock.panel.width() == 320  # card about 320 px wide at the default text size


def test_steps_that_mention_the_menu_point_at_it_while_read(dock_setup):
    s = dock_setup
    s.listeners.append(FakeListener("how do I open my extensions"))
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.state == SPEAKING)
    steps = s.dock.card.visible_steps
    menu = next(i for i, step in enumerate(steps) if target_for(step) == "menu")  # Chrome step 2: "select More (the three dots..."
    assert s.dock.walk is None                                     # alternatives, not a sequence: read, not walked
    s.dock.tts.calls[-1].line(menu + 1)
    assert s.pointed[-1] == (steps[menu], 12345)
    s.dock.escape(); s.dock.escape()
    assert s.pointed[-1] is None  # highlights removed when the card closes


def test_on_the_lms_its_guide_answers_with_evidence_and_never_points_at_browser_buttons(dock_setup, monkeypatch):
    s = dock_setup
    monkeypatch.setattr("cua.dock.window_title", lambda hwnd: "Sakai : Computer Security : Favourites - Google Chrome")
    s.listeners.append(FakeListener("how do I add a course to my top bar"))
    s.window.summon()
    assert s.dock.context_platform == "lms"
    assert wait_for(s.app, lambda: s.dock.state == SPEAKING)
    assert s.dock.answer.apps == ("lms",) and s.dock.walk is None
    assert "walkthrough video" not in s.dock.card.note.text() and not hasattr(s.dock.card, "evidence")  # the source video is not shown
    star = next(i for i, step in enumerate(s.dock.card.visible_steps) if "star" in step)  # would match the browser's star
    s.dock.tts.calls[-1].line(star + 1)
    assert not [p for p in s.pointed if p]


def test_a_new_answer_replaces_the_old_steps_immediately():
    app = QApplication.instance() or QApplication([])
    card = AnswerCard()
    card.show()
    first = Answer("First", ("edge",), ("One.", "Two.", "Three."), (), True)
    second = Answer("Second", ("edge",), ("Alpha.", "Beta."), (), True)
    card.show_answer(first, LIGHT)
    card.show_answer(second, LIGHT)  # no event-loop pass in between
    shown = [label.text() for label in card.findChildren(QLabel, "step") if label.isVisible()]
    assert len(shown) == 2 and "Alpha." in shown[0] and "Beta." in shown[1]


# ---- guided steps inside the LMS page -----------------------------------------------------------------------
LMS_COURSES = ["Computer Security (Class No 101765) - Fall 2026", "HUMAN COMPUTER INTERACTION (Class No 101624) - Fall 2026",
               "Introduction to Cloud Computing ( Class : 102201 ) Fall 2026"]
BOXES = {"course": (500, 260, 900, 300), "link: Assignments": (20, 480, 240, 520), "control: Proceed|Submit": (280, 700, 380, 740),
         "control: Submit": (300, 500, 400, 540), "link: Week 08 Reading": (288, 659, 431, 683),
         "link: Week 07 Reading": (288, 704, 431, 728), "link: Course Outline": (291, 646, 409, 670)}
SUMMARY = "Read the paper and answer three questions about it in under 400 words."


@pytest.fixture
def lms_dock(dock_setup, monkeypatch):
    from PySide6.QtCore import QRect
    s = dock_setup
    monkeypatch.setattr("cua.pagewalk.PAGE_SETTLE_MS", 10)
    monkeypatch.setattr("cua.dock.window_title", lambda hwnd: s.title)
    s.title = "Sakai : Home : Overview - Google Chrome"
    s.looked = []
    s.dock.page_courses = lambda hwnd: list(LMS_COURSES)
    s.dock.page_find = lambda hwnd, spec, chosen: (s.looked.append((spec, chosen)), (BOXES.get(spec), False))[1]
    s.seen, s.vision = [], lambda spec: None   # the vision fallback: a fake that, by default, sees nothing
    s.dock.page_seer = lambda hwnd, spec, chosen, step: (s.seen.append(spec), s.vision(spec))[1]
    s.rows, s.opened, s.summaries = [], None, []   # the Assignments list and the opened assignment, as read
    s.pressed, s.press_ok = [], True                # links Klicky opened itself ("show me the syllabus")
    s.dock.page_press = lambda hwnd, spec, chosen: (s.pressed.append(spec), s.press_ok)[1]
    s.dock.page_reader = SimpleNamespace(assignments=lambda hwnd: list(s.rows), opened=lambda hwnd: s.opened,
                                         summarize=lambda title, text: (s.summaries.append((title, text)), SUMMARY)[1])
    rect = lambda b: QRect(b[0], b[1], b[2] - b[0], b[3] - b[1])
    s.dock.highlighter.show_page = lambda b: (s.pointed.append(("page", b)), s.dock.guide_companion(rect(b)))
    s.dock.highlighter.clear = lambda: (s.pointed.append(None), s.dock.guide_companion(None))
    s.rect = rect
    return s


def click(s, box):
    from PySide6.QtCore import QPoint
    r = s.rect(box)
    s.dock.walk.clicked(QPoint(r.center()))


def say(s, text):
    s.listeners.append(FakeListener(text))


def test_lms_asks_which_course_then_points_at_each_link_and_waits_for_clicks(lms_dock):
    s = lms_dock
    dock = s.dock
    say(s, "how do I upload my assignment")
    s.window.summon()
    assert wait_for(s.app, lambda: dock.state == SPEAKING and dock.choice)
    assert dock.card.title.text() == "Which course?" and len(dock.card.step_labels) == 3
    question = dock.tts.calls[-1]
    assert question.lines[0] == "Which course? Computer Security, Human Computer Interaction, or Introduction to Cloud Computing."
    say(s, "HCI")
    question.end()                                          # Klicky listens for the answer right away
    assert wait_for(s.app, lambda: dock.walk is not None and dock.state == SPEAKING)
    step = dock.tts.calls[-1]
    assert step.lines[0] == "Okay, Human Computer Interaction." and "Human Computer Interaction" in step.lines[1]
    step.line(1)                                            # reading step 1: point at the course's tab
    assert wait_for(s.app, lambda: ("page", BOXES["course"]) in s.pointed)
    assert s.looked[-1] == ("course", LMS_COURSES[1])
    step.end()
    assert dock.state == WAITING and s.captions[-1] == "Your turn: open Human Computer Interaction from the course tabs at the top."
    click(s, BOXES["link: Assignments"])                    # a click somewhere else isn't the step
    assert dock.state == WAITING
    click(s, BOXES["course"])
    assert wait_for(s.app, lambda: dock.walk.index == 1 and dock.state == SPEAKING)
    assert len(dock.card.step_labels) == 1 and "Step 2 of 6" in dock.card.step_labels[0].text()  # only the current step
    dock.tts.calls[-1].line(0); dock.tts.calls[-1].end()
    assert wait_for(s.app, lambda: ("page", BOXES["link: Assignments"]) in s.pointed and dock.state == WAITING)
    calls = len(dock.tts.calls)
    click(s, BOXES["link: Assignments"])
    for index in (2, 3):                                    # choose the assignment, type the answer: any click
        assert wait_for(s.app, lambda: dock.walk.index == index and dock.state == SPEAKING and len(dock.tts.calls) > calls)
        calls = len(dock.tts.calls)
        dock.tts.calls[-1].line(0); dock.tts.calls[-1].end()
        assert dock.pointed_rect is None
        dock.walk.clicked(__import__("PySide6.QtCore").QtCore.QPoint(900, 900))
    assert wait_for(s.app, lambda: dock.walk.index == 4 and dock.state == SPEAKING)
    assert "Proceed" in dock.tts.calls[-1].lines[0]         # the live page's button: Proceed, then Submit next
    dock.tts.calls[-1].line(0); dock.tts.calls[-1].end()
    assert wait_for(s.app, lambda: ("page", BOXES["control: Proceed|Submit"]) in s.pointed and dock.state == WAITING)
    click(s, BOXES["control: Proceed|Submit"])
    assert wait_for(s.app, lambda: dock.walk.index == 5 and dock.state == SPEAKING)
    dock.tts.calls[-1].line(0); dock.tts.calls[-1].end()
    assert wait_for(s.app, lambda: ("page", BOXES["control: Submit"]) in s.pointed)
    walk = dock.walk
    click(s, BOXES["control: Submit"])
    assert dock.tts.calls[-1].lines == ["That's it, well done."] and not walk.active
    dock.tts.calls[-1].end()
    assert dock.state == DONE


def test_a_course_named_in_the_question_skips_the_question_and_step_one_if_already_there(lms_dock):
    s = lms_dock
    s.title = "Sakai : Computer Security (Class No 101765) - Fall 2026 : Overview - Google Chrome"
    say(s, "how do I submit my computer security assignment")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == SPEAKING)
    assert s.dock.choice is None and s.dock.walk.index == 1
    assert s.dock.tts.calls[-1].lines[0] == "Okay, Computer Security. You're already in Computer Security."


def test_an_unclear_course_is_asked_again_then_given_up_and_typing_works(lms_dock):
    s = lms_dock
    say(s, "how do I submit an assignment")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.state == SPEAKING and s.dock.choice)
    say(s, "biology")
    s.dock.tts.calls[-1].end()
    assert wait_for(s.app, lambda: s.dock.state == SPEAKING and s.dock.tts.calls[-1].lines[0].startswith("Sorry, which course?"))
    s.dock.tts.calls[-1].end()
    assert wait_for(s.app, lambda: s.dock.state == LISTENING or s.dock.state == THINKING)
    s.dock.start_typing("")                                 # the person types instead
    s.dock.input.setText("cloud")
    s.dock.submit_typed()
    assert wait_for(s.app, lambda: s.dock.walk is not None)
    assert "Introduction to Cloud Computing" in s.dock.answer.steps[0]


def test_off_the_lms_or_unreadable_page_reads_the_steps_without_asking(lms_dock):
    s = lms_dock
    s.dock.page_courses = lambda hwnd: []
    say(s, "how do I submit an assignment")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.state == SPEAKING)
    assert s.dock.choice is None and s.dock.walk is None and "your course" in s.dock.answer.steps[0]
    s.dock.reposition()
    s.app.processEvents()
    for label in s.dock.card.step_labels:  # wrapped steps get their full height, none cut off mid-line
        assert label.height() >= label.heightForWidth(label.width())


def test_inside_a_course_it_uses_that_course_and_tips_are_read_at_the_end(lms_dock):
    s = lms_dock
    s.title = "Sakai : HUMAN COMPUTER INTERACTION (Class No 101624) - Fall 2026 : Assignments - Google Chrome"
    BOXES["link: Tests & Quizzes"] = (20, 530, 240, 570)
    say(s, "which tests do I have")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == SPEAKING)   # no "Which course?"
    walk = s.dock.walk
    assert s.dock.choice is None and walk.index == 1                                       # already there: step 1 skipped
    assert s.dock.tts.calls[-1].lines[0] == "You're in Human Computer Interaction, so I'll use it."
    s.dock.tts.calls[-1].line(1); s.dock.tts.calls[-1].end()
    assert wait_for(s.app, lambda: ("page", BOXES["link: Tests & Quizzes"]) in s.pointed and s.dock.state == WAITING)
    click(s, BOXES["link: Tests & Quizzes"])
    lines = s.dock.tts.calls[-1].lines
    assert lines[0] == "That's it, well done." and len(lines) == 3 and "Take an Assessment" in lines[1] and not walk.active
    assert "3." in s.dock.card.step_labels[0].text()   # the card shows the tips being read


def test_a_different_course_named_while_inside_one_wins(lms_dock):
    s = lms_dock
    s.title = "Sakai : HUMAN COMPUTER INTERACTION (Class No 101624) - Fall 2026 : Assignments - Google Chrome"
    say(s, "how do I see the cloud computing announcements")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == SPEAKING)
    assert s.dock.walk.index == 0 and s.dock.tts.calls[-1].lines[0] == "Okay, Introduction to Cloud Computing."



def assignment_rows():
    from cua.page import Assignment
    return [Assignment("Week 08 Reading", "In progress", "Nov 4, 2099, 2:15 PM"),
            Assignment("Week 07 Reading", "Submitted Oct 28, 2026, 2:04 PM", "Oct 28, 2026, 2:15 PM"),
            Assignment("Project Draft", "Not Started", "Sep 30, 2026, 11:55 PM")]   # past due: not offered


def to_assignment_list(s):
    """Inside Computer Security, asked how to submit: point at Assignments, click it, and the list is read."""
    s.title = "Sakai : Computer Security (Class No 101765) - Fall 2026 : Overview - Google Chrome"
    s.rows = assignment_rows()
    say(s, "how do I submit my assignment")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == SPEAKING)
    s.dock.tts.calls[-1].line(1); s.dock.tts.calls[-1].end()
    assert wait_for(s.app, lambda: ("page", BOXES["link: Assignments"]) in s.pointed and s.dock.state == WAITING)
    calls = len(s.dock.tts.calls)
    click(s, BOXES["link: Assignments"])
    assert wait_for(s.app, lambda: s.dock.walk.index == 2 and s.dock.walk.rows and len(s.dock.tts.calls) > calls)
    return s.dock.tts.calls[-1]


def test_the_assignment_step_says_what_is_not_submitted_points_at_it_and_a_named_one_already_submitted_ends_it(lms_dock):
    s = lms_dock
    question = to_assignment_list(s)
    assert question.lines == ["Which assignment? Week 08 Reading isn't submitted yet. It's due November 4 at 2:15 PM. "
                              "I'm pointing at it: click it, or tell me another one."]
    assert "Not submitted yet: Week 08 Reading (due Nov 4, 2099, 2:15 PM)" == s.dock.card.note.text()
    question.line(0)
    assert wait_for(s.app, lambda: ("page", BOXES["link: Week 08 Reading"]) in s.pointed)   # boxed, pointer on it
    say(s, "week seven")
    question.end()                                            # Klicky listens for the name
    assert wait_for(s.app, lambda: s.dock.state == SPEAKING and s.dock.tts.calls[-1].lines == ["Okay, Week 07 Reading. Click it to open it."])
    assert s.dock.walk.active and s.dock.walk.index == 2
    s.dock.tts.calls[-1].line(0)
    assert wait_for(s.app, lambda: ("page", BOXES["link: Week 07 Reading"]) in s.pointed)
    s.dock.tts.calls[-1].end()
    from cua.page import AssignmentPage
    s.opened = AssignmentPage("Week 07 Reading", True, "Oct 28, 2026, 2:04 PM", "", "Answer three questions.")
    walk = s.dock.walk
    click(s, BOXES["link: Week 07 Reading"])
    assert wait_for(s.app, lambda: not walk.active)
    assert s.dock.tts.calls[-1].lines == ["Week 07 Reading is already submitted, on October 28 at 2:04 PM. "
                                          "You don't have to worry about this one."]
    assert s.summaries == []                                  # nothing is summarized (or sent) for a submitted one
    s.dock.tts.calls[-1].end()
    assert s.dock.state == DONE


def test_a_clicked_assignment_not_submitted_gets_its_due_date_and_a_summary_then_the_next_step(lms_dock):
    s = lms_dock
    question = to_assignment_list(s)
    s.listeners.append(FakeListener(wait=True))               # nothing said: the person clicks instead
    question.line(0); question.end()
    assert wait_for(s.app, lambda: s.dock.state == LISTENING)
    from cua.page import AssignmentPage
    s.opened = AssignmentPage("Week 08 Reading", False, "", "Nov 4, 2099, 2:15 PM", "The paper is provided. Answer the questions.")
    s.dock.walk.clicked(__import__("PySide6.QtCore").QtCore.QPoint(300, 670))
    assert wait_for(s.app, lambda: s.dock.walk.index == 3 and s.dock.state == SPEAKING)
    assert s.summaries == [("Week 08 Reading", "The paper is provided. Answer the questions.")]
    lines = s.dock.tts.calls[-1].lines
    assert lines[:2] == ["Week 08 Reading isn't submitted yet. It's due November 4 at 2:15 PM.", f"Here's what it asks: {SUMMARY}"]
    assert lines[2].startswith("Read the Instructions")       # then on with the submit steps
    assert SUMMARY in s.dock.card.note.text()


def test_an_assignment_named_in_the_question_is_pointed_at_without_asking(lms_dock):
    s = lms_dock
    s.title = "Sakai : Computer Security (Class No 101765) - Fall 2026 : Assignments - Google Chrome"
    s.rows = assignment_rows()
    say(s, "how do I submit my week 8 reading")
    s.window.summon()                                         # already on the Assignments page: its link is skipped
    assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.walk.first == 2 and s.dock.walk.rows)
    assert wait_for(s.app, lambda: s.dock.tts.calls[-1].lines[-1] == "Okay, Week 08 Reading. Click it to open it.")
    assert s.dock.tts.calls[-1].lines[0] == "You're in Computer Security, so I'll use it."
    assert not s.dock.walk.asking


def test_inside_an_assignment_already_it_reads_that_page_straight_away(lms_dock):
    from cua.page import AssignmentPage
    s = lms_dock
    s.title = "Sakai : Computer Security (Class No 101765) - Fall 2026 : Assignments - Google Chrome"
    s.rows, s.opened = [], AssignmentPage("Week 07 Reading", True, "Oct 28, 2026, 2:04 PM", "", "Answer three questions.")
    say(s, "is my assignment submitted")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.tts.calls and "already submitted" in s.dock.tts.calls[-1].lines[-1])
    assert s.dock.tts.calls[-1].lines == ["Week 07 Reading is already submitted, on October 28 at 2:04 PM. "
                                          "You don't have to worry about this one."]


def test_the_course_outline_step_boxes_the_course_outline_item(lms_dock):
    s = lms_dock
    s.title = "Sakai : Computer Security (Class No 101765) - Fall 2026 : Overview - Google Chrome"
    BOXES["link: Syllabus"] = (0, 494, 250, 539)
    say(s, "where is the course outline")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == SPEAKING)
    s.dock.tts.calls[-1].line(1); s.dock.tts.calls[-1].end()
    assert wait_for(s.app, lambda: ("page", BOXES["link: Syllabus"]) in s.pointed)
    click(s, BOXES["link: Syllabus"])
    assert wait_for(s.app, lambda: s.dock.walk.index == 2 and s.dock.state == SPEAKING)
    s.dock.tts.calls[-1].line(0)
    assert wait_for(s.app, lambda: ("page", BOXES["link: Course Outline"]) in s.pointed)
    assert s.dock.pointed_rect is not None                    # the companion flies to it


def run_opening(s, count):
    """Klicky says "Opening ..." and opens that link itself, count times."""
    for _ in range(count):
        calls = len(s.dock.tts.calls)
        line = s.dock.tts.calls[-1]
        line.line(len(line.lines) - 1)
        line.end()
        assert wait_for(s.app, lambda: len(s.dock.tts.calls) > calls)


def test_show_me_the_syllabus_opens_the_course_syllabus_and_course_outline_itself(lms_dock, monkeypatch):
    monkeypatch.setattr("cua.pagewalk.PRESS_MS", 10)
    s = lms_dock
    BOXES["link: Syllabus"] = (0, 494, 250, 539)
    say(s, "show me the syllabus of computer security")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == SPEAKING)
    assert s.dock.walk.auto and s.dock.tts.calls[-1].lines == ["Okay, Computer Security.", "Opening Computer Security."]
    run_opening(s, 3)
    assert s.pressed == ["course", "link: Syllabus", "link: Course Outline"]
    assert [c.lines[-1] for c in s.dock.tts.calls[-3:-1]] == ["Opening Syllabus.", "Opening Course Outline."]
    assert ("page", BOXES["link: Course Outline"]) in s.pointed          # each one boxed before it's opened
    lines = s.dock.tts.calls[-1].lines
    assert lines[0] == "Here it is." and "Resources" in lines[1] and not s.dock.walk.active


def test_opening_assignments_itself_stops_at_choosing_one_and_never_presses_submit(lms_dock, monkeypatch):
    monkeypatch.setattr("cua.pagewalk.PRESS_MS", 10)
    s = lms_dock
    s.rows = assignment_rows()
    say(s, "open my computer security assignments")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == SPEAKING)
    run_opening(s, 2)
    assert s.pressed == ["course", "link: Assignments"]
    assert wait_for(s.app, lambda: s.dock.tts.calls[-1].lines[-1].startswith("Which assignment?"))
    assert s.dock.walk.index == 2 and s.pressed == ["course", "link: Assignments"]   # the choice is the person's


def test_when_klicky_cannot_open_a_link_the_person_clicks_it_and_is_guided(lms_dock, monkeypatch):
    monkeypatch.setattr("cua.pagewalk.PRESS_MS", 10)
    s = lms_dock
    s.press_ok = False
    say(s, "show me the syllabus of computer security")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == SPEAKING)
    run_opening(s, 1)
    assert s.dock.tts.calls[-1].lines == ["I couldn't open it myself. Please click it."] and not s.dock.walk.auto
    s.dock.tts.calls[-1].line(0); s.dock.tts.calls[-1].end()
    assert wait_for(s.app, lambda: s.dock.state == WAITING and s.dock.pointed_rect is not None)
    click(s, BOXES["course"])
    assert wait_for(s.app, lambda: s.dock.walk.index == 1)
    assert s.dock.tts.calls[-1].lines[-1] == "Select Syllabus in the left menu."          # guided from here on


def test_how_do_i_questions_are_still_guided_not_done(lms_dock):
    s = lms_dock
    say(s, "how do I see the syllabus of computer security")
    s.window.summon()
    assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == SPEAKING)
    assert not s.dock.walk.auto and s.pressed == []


def test_when_the_tree_cannot_find_a_control_the_vision_model_points_at_it(lms_dock, monkeypatch):
    from cua.vision import Seen
    s = lms_dock
    monkeypatch.setattr("cua.pagewalk.CHECK_MS", 20)
    s.title = "Sakai : Computer Security (Class No 101765) - Fall 2026 : Overview - Google Chrome"
    BOXES.pop("link: Assignments")                         # renamed or hidden: the tree finds nothing
    s.vision = lambda spec: Seen((20, 480, 240, 520)) if spec == "link: Assignments" else None
    try:
        say(s, "how do I submit my computer security assignment")
        s.window.summon()
        assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == SPEAKING)
        s.dock.tts.calls[-1].line(1); s.dock.tts.calls[-1].end()
        assert wait_for(s.app, lambda: ("page", (20, 480, 240, 520)) in s.pointed)
        from cua.pagewalk import LOOK_LIMIT
        assert set(s.seen) == {"link: Assignments"} and 1 <= len(s.seen) <= LOOK_LIMIT   # looked, within the per-step limit
        assert s.looked.count(("link: Assignments", "Computer Security (Class No 101765) - Fall 2026")) >= 2   # names first
        click(s, (20, 480, 240, 520))
        assert wait_for(s.app, lambda: s.dock.walk.index == 2)
    finally:
        BOXES["link: Assignments"] = (20, 480, 240, 520)


def test_a_control_folded_into_a_menu_points_at_the_menu_first(lms_dock, monkeypatch):
    from cua.vision import Seen
    s = lms_dock
    monkeypatch.setattr("cua.pagewalk.CHECK_MS", 20)
    monkeypatch.setattr("cua.pagewalk.CLICK_MENU_MS", 10)
    s.title = "Sakai : Computer Security (Class No 101765) - Fall 2026 : Overview - Google Chrome"
    menu = (10, 200, 50, 240)
    BOXES.pop("link: Assignments")
    s.vision = lambda spec: Seen(menu, reveals=True)        # a narrow page: the left menu is behind a menu button
    try:
        say(s, "how do I submit my computer security assignment")
        s.window.summon()
        assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == SPEAKING)
        s.dock.tts.calls[-1].line(1); s.dock.tts.calls[-1].end()
        assert wait_for(s.app, lambda: ("page", menu) in s.pointed and s.dock.walk.revealing, 8)  # slower under a full run
        assert s.captions[-1] == "It's inside this menu. Open it first."
        BOXES["link: Assignments"] = (20, 480, 240, 520)  # the menu unfolds: now the tree can see the link
        click(s, menu)
        assert s.dock.walk.index == 1                       # opening the menu isn't the step
        assert wait_for(s.app, lambda: ("page", (20, 480, 240, 520)) in s.pointed and not s.dock.walk.revealing)
        click(s, (20, 480, 240, 520))
        assert wait_for(s.app, lambda: s.dock.walk.index == 2)
    finally:
        BOXES["link: Assignments"] = (20, 480, 240, 520)


# ---- Speak or Type ------------------------------------------------------------------------------------------
def test_the_orb_toggle_and_typing_box_follow_the_spec(dock_setup):
    s = dock_setup
    s.window.summon()
    dock = s.dock
    assert dock.orb.diameter == 56                                                  # the original orb, unchanged
    toggle = dock.toggle
    assert (toggle.width(), toggle.height()) == (190, 46) and toggle.accessibleName() == "Input mode"
    voice, typing = toggle.buttons["speak"], toggle.buttons["type"]
    assert (voice.accessibleName(), voice.text(), typing.accessibleName(), typing.text()) == ("Voice", "Speak", "Typing", "Type")
    assert voice.isCheckable() and voice.isChecked() and not typing.isChecked()
    assert voice.height() >= 44 and typing.height() >= 44
    gap = toggle.geometry().top() - dock.orb.geometry().bottom() - 1
    assert 14 <= gap <= 16
    height = dock.height()
    dock.set_input_mode("type")
    assert dock.height() == height                                                  # the reserved row: nothing moves
    assert typing.isChecked() and dock.input.isVisible() and dock.state == TYPING
    dock.set_input_mode("speak")
    assert not dock.input.isVisible() and dock.state == LISTENING


def test_the_hotkey_opens_in_the_saved_mode_and_a_typed_question_is_answered_in_text_only(dock_setup, monkeypatch):
    from cua.config import load
    monkeypatch.setattr("cua.dock.SilentReader.MIN_MS", 5)
    monkeypatch.setattr("cua.dock.SilentReader.MS_PER_CHAR", 0)
    s = dock_setup
    s.window.settings = Settings(hotkey="", input_mode="type")
    dock = s.dock
    dock.silent = __import__("cua.dock", fromlist=["SilentReader"]).SilentReader(lambda line: dock.set_caption(line, whole=True))
    s.window.summon()
    assert dock.state == TYPING and dock.input.isVisible() and not s.listeners    # no microphone at all
    dock.input.setText("how do I make the text bigger in firefox")
    dock.submit_typed()
    assert wait_for(s.app, lambda: dock.state == DONE, 6)
    assert dock.tts.calls == []                                                    # nothing said aloud
    assert dock.answer.steps[-1] in " ".join(s.captions) or s.captions                 # each line shown instead
    assert dock.card.isVisible() and dock.answer.grounded                          # the answer is shown as text
    assert dock.input.isVisible() and dock.input.text() == ""                      # ready for the next question
    first = dock.answer.title
    dock.input.setText("how do I see my history in firefox")                      # typing again just works
    dock.submit_typed()
    assert wait_for(s.app, lambda: dock.answer.title != first, 6) and dock.tts.calls == []


def test_a_printable_key_or_tab_switches_speak_to_type_and_the_choice_is_remembered(dock_setup, monkeypatch):
    from PySide6.QtCore import Qt
    from cua.config import load
    s = dock_setup
    s.listeners.append(FakeListener(wait=True))
    s.window.summon()
    dock = s.dock
    assert dock.state == LISTENING and dock.input_mode == "speak"
    dock.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_H, Qt.KeyboardModifier.NoModifier, "h"))
    assert dock.input_mode == "type" and dock.state == TYPING and dock.input.text() == "h"
    assert s.window.settings.input_mode == "type" and load().input_mode == "type"   # saved (in the test's folder)
    dock.set_input_mode("speak")
    s.listeners.append(FakeListener(wait=True))
    monkeypatch.setattr(dock.orb, "hasFocus", lambda: True)  # the offscreen test screen has no keyboard focus
    assert dock.focusNextPrevChild(True) and dock.input_mode == "type"              # Tab from the orb: typing


def test_typing_the_course_and_the_assignment_works_without_a_microphone(lms_dock):
    s = lms_dock
    s.window.settings = Settings(hotkey="", input_mode="type")
    s.title = "Sakai : Home : Overview - Google Chrome"
    s.rows = assignment_rows()
    s.window.summon()
    dock = s.dock
    dock.input.setText("how do I submit my assignment")
    dock.submit_typed()
    assert wait_for(s.app, lambda: dock.state == SPEAKING and dock.choice)
    dock.tts.calls[-1].end()                                     # "Which course?" shown: the answer is typed
    assert wait_for(s.app, lambda: dock.state == TYPING)
    dock.input.setText("computer security")
    dock.submit_typed()
    assert wait_for(s.app, lambda: dock.walk is not None and dock.state == SPEAKING)
    assert "Computer Security" in dock.answer.steps[0] and not s.listeners


def test_a_typed_walkthrough_shows_one_step_and_does_not_repeat_it_as_a_caption(lms_dock, monkeypatch):
    from cua.dock import SilentReader
    monkeypatch.setattr("cua.dock.SilentReader.MIN_MS", 5)
    monkeypatch.setattr("cua.dock.SilentReader.MS_PER_CHAR", 0)
    s = lms_dock
    s.window.settings = Settings(hotkey="", input_mode="type")
    s.dock.silent = SilentReader(s.dock.show_silent)
    s.title = "Sakai : Computer Security (Class No 101765) - Fall 2026 : Overview - Google Chrome"
    s.window.summon()
    s.dock.input.setText("how do I see the announcements")
    s.dock.submit_typed()
    assert wait_for(s.app, lambda: s.dock.walk is not None and s.dock.state == WAITING)
    labels = s.dock.card.step_labels
    assert len(labels) == 1 and "Step 2 of" in labels[0].text()
    assert "You're in Computer Security, so I'll use it." in s.captions                  # the lead is shown
    assert not any(c.startswith("Select Announcements") for c in s.captions)           # the step isn't repeated
