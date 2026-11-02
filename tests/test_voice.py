"""Voice input logic with fake audio, fake microphones and real Qt widgets. No real microphone is opened."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import threading
import time
from types import SimpleNamespace
import pytest
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication
from cua.config import Settings, UserError
from cua.models import Cancelled
from cua.speech import Speaker
from cua.voice import Endpointer, Transcriber, VoiceWorker


def feed(endpointer, levels):
    for level in levels:
        result = endpointer.feed(level)
        if result:
            return result
    return None


def test_endpointer_ends_after_a_pause_following_speech():
    quiet, loud = [.002]*3, [.2]*8
    assert feed(Endpointer(), quiet + loud + [.002]*11) is None
    assert feed(Endpointer(), quiet + loud + [.002]*12) == "done"


def test_endpointer_gives_up_without_speech_and_caps_length():
    assert feed(Endpointer(no_speech_chunks=20), [.003]*25) == "no_speech"
    assert feed(Endpointer(max_chunks=40), [.002]*3 + [.3]*50) == "limit"
    assert feed(Endpointer(), [.002]*3 + [.3] + [.002]*20) is None  # a single click is not speech


def test_endpointer_adapts_to_a_noisy_room():
    endpointer = Endpointer()
    feed(endpointer, [.05, .05, .05])
    assert endpointer.threshold == pytest.approx(.15)
    assert feed(endpointer, [.08]*30) is None  # fan noise below 3x the floor never counts as speech


class FakeSegment(SimpleNamespace):
    pass


@pytest.mark.parametrize("texts,expected", [([" How do I", " zoom in?"], "How do I zoom in?"), ([" Thank you."], None), ([], None)])
def test_transcriber_joins_segments_and_drops_silence_fillers(monkeypatch, texts, expected):
    transcriber = Transcriber("base.en")
    model = SimpleNamespace(transcribe=lambda audio, **kw: ([FakeSegment(text=t) for t in texts], None))
    monkeypatch.setattr(transcriber, "_model", lambda: model)
    if expected:
        assert transcriber.transcribe([0.0], threading.Event()) == expected
    else:
        with pytest.raises(UserError):
            transcriber.transcribe([0.0], threading.Event())


def run_worker(microphone, transcriber):
    app = QApplication.instance() or QApplication([])
    worker = VoiceWorker(microphone=microphone, transcriber=transcriber)
    seen = {"stage": [], "heard": [], "failed": []}
    worker.stage.connect(seen["stage"].append)
    worker.heard.connect(seen["heard"].append)
    worker.failed.connect(seen["failed"].append)
    worker.start()
    assert worker.wait(3000)
    app.processEvents()
    return seen


def test_voice_worker_reports_what_was_heard(monkeypatch):
    monkeypatch.setattr("cua.voice.beep", lambda: None)
    mic = SimpleNamespace(record=lambda stop, on_level: (on_level(.5), [0.1])[1])
    text = SimpleNamespace(transcribe=lambda audio, stop: "how do I zoom in")
    seen = run_worker(mic, text)
    assert seen["heard"] == ["how do I zoom in"] and seen["stage"] == ["listening", "transcribing"]


def test_voice_worker_reports_problems_and_cancellation(monkeypatch):
    monkeypatch.setattr("cua.voice.beep", lambda: None)
    def no_mic(stop, on_level): raise UserError("I can't use the microphone.")
    def cancelled(stop, on_level): raise Cancelled()
    assert run_worker(SimpleNamespace(record=no_mic), None)["failed"] == ["I can't use the microphone."]
    assert run_worker(SimpleNamespace(record=cancelled), None)["stage"][-1] == "stopped"


def test_forced_speech_works_with_feedback_off_and_stop_clears_it():
    speaker = Speaker()
    speaker.say("ignored")
    assert speaker.queue.empty()
    speaker.say("answer to a spoken question", force=True)
    assert not speaker.queue.empty()
    speaker.stop()
    assert speaker.queue.empty()
    speaker.close(); speaker.thread.join(1)


class FakeListener(QThread):
    level, stage, heard, failed = Signal(float), Signal(str), Signal(str), Signal(str)
    def __init__(self, text=None, wait=False):
        super().__init__()
        self.stop_event, self.text, self.wait_for_stop = threading.Event(), text, wait
    def run(self):
        self.stage.emit("listening")
        self.level.emit(.6)
        if self.wait_for_stop:
            self.stop_event.wait(3)
            self.stage.emit("stopped")
            return
        self.stage.emit("transcribing")
        self.heard.emit(self.text)


def wait_for(app, condition, seconds=3):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.01)
    return condition()


def make_window(monkeypatch):
    from cua.ui import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Settings(hotkey=""))
    spoken = []
    monkeypatch.setattr(window.speaker, "say", lambda message, force=False: spoken.append((message, force)))
    return app, window, spoken


def test_popup_listens_on_open_answers_and_speaks_back(monkeypatch):
    app, window, spoken = make_window(monkeypatch)
    popup = window.popup
    popup.voice_factory = lambda: FakeListener("um how do I make the text bigger in chrome")
    popup.open_for("chrome", None)
    assert wait_for(app, lambda: popup.answer is not None and not popup.worker.isRunning())
    app.processEvents()
    assert popup.input.text() == "um how do I make the text bigger in chrome"
    assert popup.answer.apps == ("chrome",) and "zoom" in popup.answer.title.lower()
    assert any(force and "Step 1" in message for message, force in spoken)  # spoken even with feedback off
    assert popup.mic.text() == "Speak" and popup.level.isHidden()
    popup.hide(); window.close()


def test_typing_stops_listening_and_escape_cancels_it(monkeypatch):
    app, window, spoken = make_window(monkeypatch)
    popup = window.popup
    popup.voice_factory = lambda: FakeListener(wait=True)
    popup.open_for(None, None)
    assert wait_for(app, lambda: popup.listening and popup.mic.text() == "Stop")
    popup.input.textEdited.emit("h")
    assert wait_for(app, lambda: not popup.listening)
    popup.toggle_listening()
    assert wait_for(app, lambda: popup.listening)
    popup.escape()
    assert wait_for(app, lambda: not popup.listening) and popup.isVisible()  # first Escape only stops listening
    popup.escape()
    assert not popup.isVisible()
    window.close()


def test_spoken_search_goes_to_the_search_agent(monkeypatch):
    app, window, spoken = make_window(monkeypatch)
    searches = []
    monkeypatch.setattr(window, "run_search", searches.append)
    window.popup.voice_factory = lambda: FakeListener("search for accessible computer interfaces")
    window.popup.open_for(None, None)
    assert wait_for(app, lambda: searches == ["search for accessible computer interfaces"])
    window.close()


def test_voice_off_or_missing_model_falls_back_to_typing(monkeypatch):
    app, window, spoken = make_window(monkeypatch)
    window.popup.open_for(None, None)  # conftest: model not installed
    assert not window.popup.listening and "get_speech_model" in window.popup.status.text()
    window.popup.hide()
    from dataclasses import replace
    window.settings = replace(window.settings, voice=False)
    window.popup.voice_factory = lambda: FakeListener("ignored")
    window.popup.open_for(None, None)
    assert not window.popup.listening
    window.popup.hide(); window.close()
