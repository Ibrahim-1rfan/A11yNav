"""Guided walkthroughs: Klicky waits for each step to be done, judged by what the browser shows. Fake browser."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import threading
import time
from types import SimpleNamespace
import pytest
from PySide6.QtCore import QPoint, QRect, QThread, Signal
from PySide6.QtWidgets import QApplication
from cua.assistant import build_assistant
from cua.config import Settings
from cua.dockstate import DONE, SPEAKING, WAITING
from cua.walkthrough import actionable_steps, short_turn


def test_only_leading_pointable_steps_count():
    assert actionable_steps(["Select More, the three dots at the top right.", "Next to Zoom, select Zoom in, the plus.", "Press Ctrl and 0."]) == 2
    assert actionable_steps(["Press Ctrl and F.", "Select More, the three dots."]) == 0
    assert short_turn("Select More, the three dots at the top right of the window.") == "Your turn: select More, the three dots at the top right of the window."


class FakeTTS:
    def __init__(self): self.calls, self.voice_name, self.volume = [], "", 100
    def speak(self, lines, rate=1.0, on_line_start=None, on_end=None):
        self.calls.append(SimpleNamespace(lines=lines, line=on_line_start, end=on_end))
    def stop(self): pass
    def close(self): pass


class Browser:
    """The test decides what the browser shows: is the menu open?"""
    def __init__(self): self.menu_open, self.probes = False, []
    def probe(self, hwnd, target):
        browser = self
        class Probe(QThread):
            found = Signal(str, object)
            def run(self):
                browser.probes.append(target)
                visible = target == "menu" or (target in ("zoom", "menusettings") and browser.menu_open)
                self.found.emit(target, (1500, 200, 1700, 240) if visible else None)
        return Probe()


def wait_for(app, condition, seconds=3):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.01)
    return condition()


@pytest.fixture
def walk_setup(monkeypatch):
    from cua.ui import MainWindow
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("cua.dock.screen_reader_running", lambda: False)
    monkeypatch.setattr("cua.ui.foreground_app", lambda: (12345, "chrome"))
    window = MainWindow(Settings(hotkey="", voice=False))
    window.companion.timer.stop()
    dock = window.dock
    dock.tts = FakeTTS()
    dock.silent = dock.tts  # typed questions are answered in text alone; the flow is the same
    browser = Browser()
    dock.probe_factory = browser.probe
    dock.answer_factory = None  # the real assistant, so the browser context (Chrome) reaches retrieval
    pointed = []
    dock.highlighter = SimpleNamespace(point=lambda step, hwnd: pointed.append(step), clear=lambda: pointed.append(None),
                                       cache={}, prefetch=lambda steps, hwnd: None, current_target=None)
    captions = []
    original = dock.set_caption
    monkeypatch.setattr(dock, "set_caption", lambda text: (captions.append(text), original(text)))
    window.summon()
    dock.start_typing("how do I zoom in")
    dock.submit_typed()
    assert wait_for(app, lambda: dock.walk is not None and dock.state == SPEAKING)
    yield SimpleNamespace(app=app, window=window, dock=dock, browser=browser, pointed=pointed, captions=captions)
    dock.close_dock()
    window.close()


def finish_speaking(s):
    call = s.dock.tts.calls[-1]
    if call.line:
        call.line(len(call.lines) - 1)
    call.end()


def check_until(s, condition, rounds=6):
    for _ in range(rounds):
        s.dock.walk.check()
        if wait_for(s.app, lambda: not (s.dock.walk.probe and s.dock.walk.probe.isRunning()), 1) and condition():
            return True
        s.app.processEvents()
    return condition()


def test_waits_for_the_menu_then_moves_to_the_zoom_buttons(walk_setup):
    s = walk_setup
    first = s.dock.tts.calls[-1]
    assert first.lines[0] == "Here's how to make pages and text bigger." and "three dots" in first.lines[1]
    finish_speaking(s)
    assert s.dock.state == WAITING and "three dots" in s.pointed[-1]                       # pointing at the menu
    assert s.captions[-1].startswith("Your turn: select More, the three dots")
    assert not check_until(s, lambda: s.dock.state != WAITING, rounds=3)                   # menu not open: keep waiting
    s.browser.menu_open = True                                                            # the person opens the menu
    assert check_until(s, lambda: s.dock.state == SPEAKING)
    assert "Zoom in, the plus" in s.dock.tts.calls[-1].lines[0]
    finish_speaking(s)
    assert s.dock.state == WAITING and "Next to Zoom" in s.pointed[-1]                    # now the zoom buttons
    s.dock.pointed_rect = QRect(1000, 133, 133, 27)
    s.dock.walk.clicked(QPoint(10, 10))                                                   # a click elsewhere: still waiting
    assert s.dock.state == WAITING
    s.dock.walk.clicked(QPoint(1120, 145))                                                # the plus
    assert s.dock.state == SPEAKING and s.dock.tts.calls[-1].lines[0] == "That's it, well done."
    assert "Control" in s.dock.tts.calls[-1].lines[1]                                     # then the keyboard tip
    s.dock.tts.calls[-1].end()
    assert s.dock.state == DONE and s.dock.walk is None


def test_opening_the_menu_with_the_keyboard_also_counts(walk_setup):
    s = walk_setup
    finish_speaking(s)
    s.browser.menu_open = True   # Alt+F instead of a click: no click at all, the menu simply appears
    assert check_until(s, lambda: s.dock.state == SPEAKING and s.dock.walk.index == 1)


def test_menu_closing_midway_steps_back(walk_setup):
    s = walk_setup
    finish_speaking(s)
    s.browser.menu_open = True
    assert check_until(s, lambda: s.dock.state == SPEAKING)
    finish_speaking(s)
    assert check_until(s, lambda: s.dock.walk.seen)                                       # Klicky sees the open menu
    s.browser.menu_open = False                                                           # clicked away, menu gone
    assert check_until(s, lambda: s.dock.state == SPEAKING and s.dock.walk.index == 0)
    assert s.dock.tts.calls[-1].lines[0] == "The menu closed. Let's open it again."


def test_one_gentle_reminder_when_nothing_happens(walk_setup):
    s = walk_setup
    finish_speaking(s)
    s.dock.walk.waiting_since -= 25
    s.dock.walk.check()
    assert s.dock.tts.calls[-1].lines[0].startswith("When you're ready:") and s.dock.state == WAITING
    count = len(s.dock.tts.calls)
    s.dock.walk.check()
    assert len(s.dock.tts.calls) == count                                                 # only once


def test_orb_stops_guiding_and_clicks_in_the_browser_do_not_close_klicky(walk_setup, monkeypatch):
    s = walk_setup
    finish_speaking(s)
    monkeypatch.setattr("cua.dock.ctypes.windll.user32.GetAsyncKeyState", lambda key: 0x8000)
    monkeypatch.setattr("cua.dock.QCursor.pos", lambda: QPoint(5, 5))
    s.dock.button_was_down = False
    s.dock.check_outside_click()                                                          # the person clicks the browser
    assert s.dock.state == WAITING and s.dock.isVisible()
    s.dock.orb.click()
    assert s.dock.state == DONE and s.dock.walk is None


def test_settings_is_a_walkthrough_too_but_extensions_is_not():
    corpus_answer = build_assistant(Settings()).answer
    stop = threading.Event()
    settings_answer = corpus_answer("how do I open settings in Chrome", stop)
    extensions_answer = corpus_answer("how do I open my extensions in Chrome", stop)
    assert min(settings_answer.walk, actionable_steps(settings_answer.steps[:3])) == 2
    assert extensions_answer.walk == 0


def test_klicky_moves_aside_rather_than_cover_the_control_it_points_at(walk_setup):
    s = walk_setup
    dock = s.dock
    finish_speaking(s)
    covered = dock.frameGeometry().adjusted(10, 10, -10, -10)       # pretend the menu's control is under the orb
    dock.guide_companion(covered)
    assert not dock.frameGeometry().intersects(covered)
    assert not (dock.panel.isVisible() and dock.panel.frameGeometry().intersects(covered))
    elsewhere = QRect(dock.frameGeometry().right() + 400, 5, 30, 30)
    before = dock.anchor
    dock.guide_companion(elsewhere)                                  # nothing covered: Klicky stays put
    assert dock.anchor == before


def test_clicking_the_pointed_button_moves_on_without_waiting_for_the_menu(walk_setup):
    s = walk_setup
    finish_speaking(s)
    assert s.dock.state == WAITING and s.dock.walk.index == 0
    s.dock.pointed_rect = QRect(1380, 55, 60, 60)                    # the three dots, as found on screen
    s.dock.walk.clicked(QPoint(1405, 88))                            # the person just clicks them
    s.dock.walk.clicked(QPoint(1405, 88))                            # a double click does not skip a step
    assert wait_for(s.app, lambda: s.dock.state == SPEAKING and s.dock.walk.index == 1)
    assert "Zoom in, the plus" in s.dock.tts.calls[-1].lines[0]
    finish_speaking(s)
    assert s.dock.state == WAITING and s.dock.walk.index == 1
    # The menu's buttons could not be recognised: no step back, and the next click still finishes.
    s.dock.pointed_rect = None
    assert not check_until(s, lambda: s.dock.walk.index == 0, rounds=4)
    s.dock.walk.clicked(QPoint(1345, 317))                           # the plus in the real menu
    assert s.dock.state == SPEAKING and s.dock.tts.calls[-1].lines[0] == "That's it, well done."


def test_the_card_moves_off_a_wide_tab_at_the_top_of_the_page(walk_setup):
    s = walk_setup
    dock = s.dock
    finish_speaking(s)
    area = dock.screen_area(dock.anchor)
    tab = QRect(area.center().x() - 150, area.top() + 60, 300, 40)    # like a course tab in the LMS top bar
    dock.anchor = QPoint(tab.center().x(), tab.bottom() + 40)           # Klicky opened right on top of it
    dock.reposition()
    dock.guide_companion(tab)
    clear = tab.adjusted(-12, -12, 12, 12)
    assert not dock.frameGeometry().intersects(clear)
    assert not (dock.panel.isVisible() and dock.panel.frameGeometry().intersects(clear))
