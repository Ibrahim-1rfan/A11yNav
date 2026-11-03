"""The natural (Edge) voice: order, callbacks, stopping, offline fallback, cache. No network and no sound."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import threading
import time
from types import SimpleNamespace
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from cua.neural_tts import NeuralReadAloud, Synthesizer, edge_rate


def wait_for(condition, seconds=3):
    app = QApplication.instance() or QApplication([])
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.01)
    return condition()


class FakeFallback:
    def __init__(self):
        self.calls, self.stops, self.voice_name, self.volume = [], 0, "", 100
    def speak(self, lines, rate=1.0, on_line_start=None, on_end=None):
        self.calls.append(SimpleNamespace(lines=lines, line=on_line_start, end=on_end))
    def stop(self):
        self.stops += 1
    def close(self):
        pass


@pytest.fixture
def voice():
    QApplication.instance() or QApplication([])
    made, played, gate = [], [], threading.Event()
    gate.set()
    def synthesize(text, name, rate):
        made.append((text, name, rate))
        if text == "FAIL":
            raise ConnectionError("offline")
        return np.full(10, .5, np.float32)
    def player(samples, stop, volume):
        gate.wait(2)
        played.append(volume)
        return not stop()
    reader = NeuralReadAloud(synthesize=synthesize, player=player, fallback=FakeFallback())
    yield SimpleNamespace(reader=reader, made=made, played=played, gate=gate)
    reader.close()


def test_lines_play_in_order_with_a_callback_each_and_one_end(voice):
    started, ended = [], []
    voice.reader.neural_voice = "en-IN-NeerjaNeural"
    voice.reader.speak(["Here's how.", "Step one.", "Step two."], 1.2, on_line_start=started.append, on_end=lambda: ended.append(1))
    assert wait_for(lambda: ended == [1])
    assert started == [0, 1, 2] and len(voice.played) == 3
    assert [m[0] for m in voice.made] == ["Here's how.", "Step one.", "Step two."]
    assert all(m[1:] == ("en-IN-NeerjaNeural", 1.2) for m in voice.made)


def test_stop_silences_and_never_calls_the_end(voice):
    started, ended = [], []
    voice.gate.clear()                     # the first line is "playing" until released
    voice.reader.speak(["One.", "Two.", "Three."], on_line_start=started.append, on_end=lambda: ended.append(1))
    assert wait_for(lambda: started == [0])
    voice.reader.stop()
    voice.gate.set()
    time.sleep(.3)
    wait_for(lambda: False, .3)
    assert ended == [] and started == [0] and voice.reader.fallback.stops >= 1


def test_offline_hands_the_rest_to_the_windows_voice_with_the_same_callbacks(voice):
    started, ended = [], []
    voice.reader.voice_name = "Microsoft Zira Desktop"
    voice.reader.speak(["Intro.", "FAIL", "Last."], on_line_start=started.append, on_end=lambda: ended.append(1))
    assert wait_for(lambda: voice.reader.fallback.calls)
    call = voice.reader.fallback.calls[0]
    assert call.lines == ["FAIL", "Last."] and voice.reader.fallback.voice_name == "Microsoft Zira Desktop"
    call.line(0); call.line(1); call.end()  # the Windows voice reads them: indexes continue where it left off
    assert started == [0, 1, 2] and ended == [1]


def test_cache_means_each_line_is_fetched_once(tmp_path, monkeypatch):
    fetched = []
    monkeypatch.setattr("cua.neural_tts.decode", lambda mp3: np.frombuffer(mp3, np.uint8).astype(np.float32))
    synth = Synthesizer(tmp_path, fetch=lambda text, voice, rate: fetched.append(text) or b"\x01\x02")
    assert len(synth("Select Drop Box.", "en-US-AvaNeural", 1.0)) == 2
    assert len(synth("Select Drop Box.", "en-US-AvaNeural", 1.0)) == 2
    synth("Select Drop Box.", "en-US-AvaNeural", 1.2)          # another speed is another recording
    assert fetched == ["Select Drop Box.", "Select Drop Box."] and len(list(tmp_path.iterdir())) == 2
    with pytest.raises(RuntimeError):
        Synthesizer(tmp_path, fetch=lambda *a: b"")("Nothing came back.", "en-US-AvaNeural", 1.0)


def test_rates_and_settings():
    from cua.config import Settings, UserError
    assert (edge_rate(1.0), edge_rate(.8), edge_rate(1.2)) == ("+0%", "-20%", "+20%")
    assert Settings().voice_engine == "natural" and Settings().neural_voice == "en-US-AvaNeural"
    with pytest.raises(UserError):
        Settings(neural_voice="en-US-Ava; rm -rf").validate()
    with pytest.raises(UserError):
        Settings(voice_engine="robot").validate()


def test_the_dock_switches_voices_with_the_setting_and_keeps_windows_as_fallback():
    from dataclasses import replace
    from cua.config import Settings
    from cua.neural_tts import NeuralReadAloud
    from cua.tts import ReadAloud
    from cua.ui import MainWindow
    QApplication.instance() or QApplication([])
    window = MainWindow(Settings(hotkey=""))
    dock = window.dock
    windows_voice = dock.tts
    assert type(windows_voice) is ReadAloud
    reader = dock.reader()
    assert isinstance(reader, NeuralReadAloud) and reader.fallback is windows_voice and reader.neural_voice == "en-US-AvaNeural"
    window.settings = replace(window.settings, voice_engine="windows")
    assert dock.reader() is windows_voice
    reader.close()
    window.close()


def test_prewarm_caches_each_common_line_once_in_the_background(voice):
    from cua.dock import common_lines
    lines = common_lines()
    assert "That's it, well done." in lines and not any("{" in line for line in lines)
    voice.reader.prewarm(["A.", "B.", "A."])
    assert wait_for(lambda: sorted(m[0] for m in voice.made) == ["A.", "B."])
