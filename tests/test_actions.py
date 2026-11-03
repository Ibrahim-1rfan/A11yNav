"""Klicky doing simple browser tasks: only a fixed list, the real button pressed, keyboard as fallback. All faked."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import threading
import time
from types import SimpleNamespace
import pytest
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication
from cua.browser_actions import SPECS, ActionWorker
from cua.config import Settings
from cua.dockstate import ACTING, DONE, SPEAKING
from cua.planning import BrowserAction, HelpQuestion, route


@pytest.mark.parametrize("text,action", [
    ("open a new tab for me", "newtab"), ("Open a new page", "newtab"), ("can you refresh the page for me?", "refresh"),
    ("refresh it", "refresh"), ("please reload", "refresh"), ("zoom in the screen for me", "zoomin"),
    ("make it bigger", "zoomin"), ("zoom out please", "zoomout"), ("reset zoom", "zoomreset"), ("go back a page for me", "back"),
    ("go forward", "forward"), ("close this tab", "closetab"), ("cancel this page", "closetab"), ("reopen the tab", "reopen"),
    ("bookmark this page", "bookmark"), ("add this to my favorites", "bookmark"), ("open my history", "history"),
    ("open the settings for me", "settings"), ("open my extensions", "extensions"), ("Klicky, open a new tab", "newtab"),
])
def test_short_requests_name_one_allowed_action(text, action):
    result = route(text, "bing")
    assert isinstance(result, BrowserAction) and result.action == action and action in SPECS


@pytest.mark.parametrize("text", ["how do I zoom in", "how do I open a new tab in Edge", "where are my extensions"])
def test_questions_still_get_guidance(text):
    assert isinstance(route(text, "bing"), HelpQuestion)


@pytest.mark.parametrize("text", ["open a new tab and search for cats", "close the tab and then buy something",
                                  "delete my files", "zoom in on the picture of my bank account password"])
def test_anything_else_is_never_acted_on(text):
    try:
        result = route(text, "bing")
    except Exception:
        result = None
    assert not isinstance(result, BrowserAction)


class FakeLocator:
    def __init__(self, found=True):
        self.found = found
        self.info = object() if found else None
    def __call__(self, hwnd, target):
        self.target = target
        return self
    def locate(self):
        return (100, 10, 140, 50) if self.found else None


def run_worker(action, locator=None, invoke_ok=True, forward=True, monkeypatch=None):
    app = QApplication.instance() or QApplication([])
    keys, events = [], []
    if monkeypatch:
        class Wrapper:
            def __init__(self, info): pass
            def invoke(self):
                if not invoke_ok:
                    raise RuntimeError("no invoke pattern")
                events.append("invoked")
        monkeypatch.setattr("pywinauto.controls.uiawrapper.UIAWrapper", Wrapper)
        monkeypatch.setattr("cua.browser_actions.FLY_S", .01)
        monkeypatch.setattr("cua.browser_actions.PRESS_S", .01)
    worker = ActionWorker(4242, action, "edge", locator_factory=locator or FakeLocator(), keys=keys.append, foreground=lambda: forward)
    worker.located.connect(lambda rect: events.append(("located", rect)))
    worker.pressing.connect(lambda: events.append("pressing"))
    worker.done.connect(lambda message: events.append(("done", message)))
    worker.failed.connect(lambda message: events.append(("failed", message)))
    worker.start()
    assert worker.wait(3000)
    app.processEvents()
    return events, keys


def test_presses_the_real_button_without_touching_the_mouse(monkeypatch):
    events, keys = run_worker("newtab", monkeypatch=monkeypatch)
    assert "invoked" in events                                         # the real button was pressed
    assert [e for e in events if e != "invoked"] == [("located", (100, 10, 140, 50)), "pressing", ("done", "Opened a new tab.")]
    assert keys == []


def test_falls_back_to_the_shortcut_when_the_button_cannot_be_pressed(monkeypatch):
    events, keys = run_worker("refresh", invoke_ok=False, monkeypatch=monkeypatch)
    assert keys == [("f5",)] and events[-1] == ("done", "Refreshed the page.")
    events, keys = run_worker("back", locator=FakeLocator(found=False), monkeypatch=monkeypatch)
    assert keys == [("alt", "left")] and events[0] == ("located", None)


def test_zoom_uses_the_keyboard_and_an_unreachable_browser_is_reported(monkeypatch):
    events, keys = run_worker("zoomin", monkeypatch=monkeypatch)
    assert keys == [("ctrl", "=")] and events[-1][0] == "done"
    events, keys = run_worker("zoomout", forward=False, monkeypatch=monkeypatch)
    assert keys == [] and events[-1][0] == "failed" and "browser window" in events[-1][1]


def test_settings_opens_the_browsers_own_page_in_a_new_tab(monkeypatch):
    opened = []
    monkeypatch.setattr(ActionWorker, "open_page", lambda self, page: opened.append(page))
    events, keys = run_worker("settings", monkeypatch=monkeypatch)
    assert opened == ["edge://settings"] and events[-1] == ("done", "Opened settings in a new tab.")


# ---- the dock doing it ---------------------------------------------------------------------------------
class FakeActor(QThread):
    located, pressing, done, failed = Signal(object), Signal(), Signal(str), Signal(str)
    made = []
    def __init__(self, hwnd, action, app):
        super().__init__()
        self.action, self.stop_event = action, threading.Event()
        FakeActor.made.append(self)
    def run(self):
        self.located.emit((100, 10, 140, 50))
        time.sleep(.05)
        self.pressing.emit()
        self.done.emit(SPECS[self.action]["done"])


class FakeTTS:
    def __init__(self): self.calls, self.voice_name, self.volume = [], "", 100
    def speak(self, lines, rate=1.0, on_line_start=None, on_end=None): self.calls.append(lines)
    def stop(self): pass
    def close(self): pass


def wait_for(app, condition, seconds=3):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.01)
    return condition()


@pytest.fixture
def acting(monkeypatch):
    from cua.ui import MainWindow
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("cua.dock.screen_reader_running", lambda: False)
    monkeypatch.setattr("cua.ui.foreground_app", lambda: (12345, "edge"))
    window = MainWindow(Settings(hotkey="", voice=False))
    window.companion.timer.stop()
    dock = window.dock
    dock.tts = FakeTTS()
    dock.silent = dock.tts  # typed questions are answered in text alone; the flow is the same
    dock.action_factory = FakeActor
    presses = []
    monkeypatch.setattr(window.companion, "press", lambda: presses.append(True))
    FakeActor.made.clear()
    yield SimpleNamespace(app=app, window=window, dock=dock, presses=presses)
    dock.close_dock()
    window.close()


def ask(s, text):
    s.window.summon()
    s.dock.start_typing(text)
    s.dock.submit_typed()


def test_open_a_new_tab_for_me(acting):
    s = acting
    ask(s, "open a new tab for me")
    assert s.dock.state == ACTING and s.dock.caption.text() == "Opening a new tab..."
    assert wait_for(s.app, lambda: s.dock.state == DONE)
    assert FakeActor.made[-1].action == "newtab" and s.presses == [True]          # the companion "clicked" it
    assert s.dock.caption.text() == "Opened a new tab." and s.dock.tts.calls[-1] == ["Opened a new tab."]
    s.dock.auto_close.timeout.emit()                                              # a few seconds later
    assert s.dock.state == "closed"


def test_actions_off_means_guidance_instead(acting):
    s = acting
    s.window.settings = Settings(hotkey="", voice=False, actions=False)
    ask(s, "open a new tab")
    assert wait_for(s.app, lambda: s.dock.state in (SPEAKING, DONE) and s.dock.answer is not None)
    assert FakeActor.made == [] and s.dock.answer.title == "Open a new tab or window"


def test_how_do_i_questions_are_guided_not_done(acting):
    s = acting
    ask(s, "how do I open a new tab")
    assert wait_for(s.app, lambda: s.dock.answer is not None)
    assert FakeActor.made == []


@pytest.mark.parametrize("text,action", [
    ("Can you open a new tab?", "newtab"), ("can you open another tab for me", "newtab"), ("can you open a tab", "newtab"),
    ("Could you please open a new tab?", "newtab"), ("can u open a new tab", "newtab"), ("Can you refresh this page?", "refresh"),
    ("can you take me back", "back"), ("can you go to the previous page", "back"), ("can you go back to the last page", "back"),
    ("Can you zoom in?", "zoomin"), ("can you zoom in a bit", "zoomin"), ("can you make the text bigger", "zoomin"),
    ("can you increase the zoom", "zoomin"), ("can you make it smaller", "zoomout"), ("can you decrease the zoom", "zoomout"),
    ("can you make it normal size", "zoomreset"), ("can you reset the zoom", "zoomreset"), ("can you close the page", "closetab"),
    ("can you reopen the tab I closed", "reopen"), ("can you bring back the tab", "reopen"), ("can you bookmark this", "bookmark"),
    ("can you add this page to favorites", "bookmark"), ("can you show my history", "history"), ("can you show me my history", "history"),
    ("can you open the browser settings", "settings"), ("can you show my extensions", "extensions"),
])
def test_can_you_requests_are_done(text, action):
    result = route(text, "bing")
    assert isinstance(result, BrowserAction) and result.action == action


@pytest.mark.parametrize("text", ["can you show me how to zoom in", "can you tell me how to open a new tab", "can you help me open a new tab"])
def test_can_you_show_me_how_is_still_a_question(text):
    assert isinstance(route(text, "bing"), HelpQuestion)


@pytest.mark.parametrize("text", ["can you delete my history", "can you open a new tab and search for cats", "can you save this file"])
def test_can_you_with_anything_else_is_not_done(text):
    try:
        result = route(text, "bing")
    except Exception:
        result = None
    assert not isinstance(result, BrowserAction)
