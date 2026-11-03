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
from cua.dockstate import CLOSED, DONE, ERROR, IDLE, LISTENING, SPEAKING, THINKING, TYPING, DockState
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
    listeners, monitors, captions, focused = [], [], [], []
    dock.voice_factory = lambda: listeners[-1] if listeners and not listeners[-1].isRunning() and not listeners[-1].isFinished() else listeners.append(FakeListener("how do I make the text bigger in firefox")) or listeners[-1]
    dock.monitor_factory = lambda: monitors.append(FakeMonitor()) or monitors[-1]
    dock.answer_factory = lambda: build_assistant(Settings())
    pointed = []
    dock.highlighter = SimpleNamespace(point=lambda step, hwnd: pointed.append((step, hwnd)), clear=lambda: pointed.append(None), cache={},
                                       prefetch=lambda steps, hwnd: None)
    original = dock.set_caption
    monkeypatch.setattr(dock, "set_caption", lambda text: (captions.append(text), original(text)))
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
