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
    quiet, loud = [.002]*3, [.2]*8          # 50 ms readings: 150 ms floor, 400 ms of speech
    assert feed(Endpointer(), quiet + loud + [.002]*23) is None   # 1.15 s of quiet: still listening
    assert feed(Endpointer(), quiet + loud + [.002]*24) == "done"  # 1.2 s of quiet ends the question


def test_endpointer_gives_up_without_speech_and_caps_length():
    assert feed(Endpointer(no_speech_ms=1000), [.003]*25) == "no_speech"
    assert feed(Endpointer(max_ms=2000), [.002]*3 + [.3]*50) == "limit"
    assert feed(Endpointer(), [.002]*3 + [.3] + [.002]*40) is None  # a single 50 ms click is not speech


def test_endpointer_adapts_to_a_noisy_room():
    endpointer = Endpointer()
    feed(endpointer, [.05, .05, .05])
    assert endpointer.threshold == pytest.approx(.15)
    assert feed(endpointer, [.08]*60) is None  # fan noise below 3x the floor never counts as speech


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
    mic = SimpleNamespace(record=lambda stop, on_level, **kw: (on_level(.5), [0.1])[1])
    text = SimpleNamespace(transcribe=lambda audio, stop: "how do I zoom in")
    seen = run_worker(mic, text)
    assert seen["heard"] == ["how do I zoom in"] and seen["stage"] == ["listening", "transcribing"]


def test_voice_worker_reports_problems_and_cancellation(monkeypatch):
    monkeypatch.setattr("cua.voice.beep", lambda: None)
    def no_mic(stop, on_level, **kw): raise UserError("I can't use the microphone.")
    def cancelled(stop, on_level, **kw): raise Cancelled()
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


@pytest.mark.skipif(os.name != "nt", reason="uses Windows speech")
def test_stop_silences_real_windows_speech_immediately():
    speaker = Speaker()
    speaker.volume = 0  # real SAPI speech, inaudible during tests
    speaker.say("Step one. To zoom in, press Control and Plus together. " * 6, force=True)
    deadline = time.monotonic() + 5
    while not speaker.speaking and time.monotonic() < deadline:
        time.sleep(.01)
    assert speaker.speaking
    time.sleep(.5)
    started = time.monotonic()
    speaker.stop()
    while speaker.speaking and time.monotonic() < started + 2:
        time.sleep(.005)
    assert not speaker.speaking and speaker.stopped_cleanly
    assert speaker.cut_at - started < .1  # muted within 100 ms of Stop
    speaker.close(); speaker.thread.join(1)


class GroqReply:
    def __init__(self, text, status=200):
        self.text, self.status = text, status
    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(self.status)
    def json(self):
        return {"text": self.text}


def test_groq_is_used_only_on_auto_with_a_key(monkeypatch):
    from cua.voice import HostedTranscriber, hosted, transcriber_for
    from cua.config import Settings
    assert not hosted(Settings()) and isinstance(transcriber_for(Settings()), Transcriber)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    assert hosted(Settings()) and isinstance(transcriber_for(Settings()), HostedTranscriber)
    assert not hosted(Settings(speech_service="local")) and isinstance(transcriber_for(Settings(speech_service="local")), Transcriber)
    with pytest.raises(UserError):
        Settings(speech_service="cloud").validate()


def test_groq_gets_the_clip_as_wav_and_its_text_is_used(monkeypatch):
    import numpy as np
    from cua import voice
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    sent = []
    post = lambda url, **kw: (sent.append((url, kw)), GroqReply("  How do I submit my week 8 reading? "))[1]
    hosted = voice.HostedTranscriber(Transcriber("base.en"), post)
    assert hosted.transcribe(np.zeros(16000, dtype=np.float32), threading.Event()) == "How do I submit my week 8 reading?"
    url, kw = sent[0]
    assert url == voice.GROQ_URL and kw["allow_redirects"] is False and kw["headers"]["Authorization"] == "Bearer test-key"
    name, audio, kind = kw["files"]["file"]
    assert audio[:4] == b"RIFF" and kind == "audio/wav" and len(audio) == 44 + 32000   # one second, 16-bit, in memory
    assert kw["data"]["model"] == "whisper-large-v3-turbo" and kw["data"]["language"] == "en"
    assert hosted.partial([0.0]) == ""   # captions never go to Groq (and here no local model is installed)
    with pytest.raises(UserError):        # a filler on silence is still "nothing heard"
        voice.HostedTranscriber(Transcriber("base.en"), lambda url, **kw: GroqReply("Thank you.")).transcribe([0.0], threading.Event())


def test_a_failed_groq_call_falls_back_to_this_pc_or_says_so(monkeypatch):
    from cua import voice
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    def down(url, **kw):
        raise TimeoutError()
    local = SimpleNamespace(name="base.en", transcribe=lambda audio, stop: "zoom in", partial=lambda audio: "zoom")
    with pytest.raises(UserError, match="speech service"):
        voice.HostedTranscriber(local, down).transcribe([0.0], threading.Event())
    monkeypatch.setattr(voice, "model_installed", lambda name: True)
    hosted = voice.HostedTranscriber(local, lambda url, **kw: GroqReply("", 500))
    assert hosted.transcribe([0.0], threading.Event()) == "zoom in" and hosted.partial([0.0]) == "zoom"
