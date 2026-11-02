"""Local voice input: microphone capture with automatic end-of-speech detection, then on-device Whisper.

Audio stays in memory on this computer. It is never written to disk, logged or sent anywhere.
"""
from dataclasses import dataclass
import os
import threading
from PySide6.QtCore import QThread, Signal
from .config import UserError, settings_path
from .models import Cancelled

RATE = 16000
CHUNK = 1600  # 100 ms
# Primes Whisper with the words Klicky's questions use, so "Chrome" is not heard as "crow".
VOCABULARY = ("Questions about the web browsers Chrome, Edge and Firefox: zoom, text size, reader mode, read aloud, "
              "dark mode, captions, caret browsing, tabs, bookmarks, favorites, history.")
MODELS = {"tiny.en": "Systran/faster-whisper-tiny.en", "base.en": "Systran/faster-whisper-base.en",
          "small.en": "Systran/faster-whisper-small.en"}


def model_dir(name):
    return settings_path().parent / "models" / f"faster-whisper-{name}"


def model_installed(name):
    path = model_dir(name)
    return (path / "model.bin").exists() and (path / "config.json").exists()


@dataclass
class Endpointer:
    """Decides when speech started and ended from 100 ms loudness readings.

    The first readings set a noise floor; speech is anything clearly above it. Listening ends after a
    pause following speech, at a hard length limit, or when nobody speaks at all.
    """
    pause_chunks: int = 12       # 1.2 s of quiet ends the question
    max_chunks: int = 150        # 15 s hard limit
    no_speech_chunks: int = 70   # give up after 7 s with no speech
    floor_chunks: int = 3
    min_level: float = .012

    def __post_init__(self):
        self.levels, self.speech_chunks, self.quiet = [], 0, 0

    @property
    def threshold(self):
        floor = sorted(self.levels[:self.floor_chunks])[len(self.levels[:self.floor_chunks]) // 2] if self.levels else 0
        return max(self.min_level, floor * 3)

    def feed(self, level):
        """Return None to keep listening, or "done", "no_speech" or "limit"."""
        self.levels.append(level)
        if len(self.levels) <= self.floor_chunks:
            return None
        if level >= self.threshold:
            self.speech_chunks += 1
            self.quiet = 0
        elif self.speech_chunks:
            self.quiet += 1
        if self.speech_chunks >= 2 and self.quiet >= self.pause_chunks:
            return "done"
        if len(self.levels) >= self.max_chunks:
            return "limit" if self.speech_chunks >= 2 else "no_speech"
        if not self.speech_chunks and len(self.levels) >= self.no_speech_chunks:
            return "no_speech"
        return None


class Microphone:
    """Records one spoken question from the default input device."""
    def record(self, stop, on_level, endpointer=None):
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError as exc:
            raise UserError("Voice input is not installed. Run scripts\\setup.bat again.") from exc
        endpointer = endpointer or Endpointer()
        chunks = []
        try:
            with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=CHUNK) as stream:
                while True:
                    if stop.is_set():
                        raise Cancelled()
                    data, _ = stream.read(CHUNK)
                    mono = data[:, 0].copy()
                    chunks.append(mono)
                    level = float(np.sqrt(np.mean(mono * mono)))
                    on_level(min(1.0, level / max(endpointer.threshold * 4, .05)))
                    result = endpointer.feed(level)
                    if result == "no_speech":
                        raise UserError("I didn't hear anything. Press the microphone button or type your question.")
                    if result:
                        return np.concatenate(chunks)
        except sd.PortAudioError as exc:
            raise UserError("I can't use the microphone. Check that one is connected and that Windows Settings > Privacy > Microphone allows desktop apps.") from exc


class Transcriber:
    """On-device Whisper. The model loads once and is reused."""
    _lock = threading.Lock()
    _models = {}

    def __init__(self, name="base.en"):
        self.name = name

    def _model(self):
        if not model_installed(self.name):
            raise UserError("The speech model is not installed yet. Run scripts\\get_speech_model.bat once.")
        with self._lock:
            if self.name not in self._models:
                from faster_whisper import WhisperModel
                threads = max(1, min(4, (os.cpu_count() or 2) - 1))
                self._models[self.name] = WhisperModel(str(model_dir(self.name)), device="cpu", compute_type="int8", cpu_threads=threads)
            return self._models[self.name]

    def transcribe(self, audio, stop):
        model = self._model()
        if stop.is_set():
            raise Cancelled()
        segments, _ = model.transcribe(audio, language="en", beam_size=5, vad_filter=True, initial_prompt=VOCABULARY,
                                       condition_on_previous_text=False, without_timestamps=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if stop.is_set():
            raise Cancelled()
        # Whisper can invent a polite filler on near-silence; treat that as nothing heard.
        if not text or text.lower().strip(" .!?") in {"thank you", "thanks", "you", "bye", "thanks for watching"}:
            raise UserError("I didn't catch that. Please try again, or type your question.")
        return text


def preload(name):
    """Load the speech model in the background at startup so the first question is not slow."""
    def load():
        try:
            if model_installed(name):
                Transcriber(name)._model()
        except Exception:
            pass  # the first real question reports any problem in words
    threading.Thread(target=load, daemon=True).start()


def beep():
    if os.name == "nt":
        try:
            import winsound
            winsound.Beep(880, 90)
        except RuntimeError:
            pass


class VoiceWorker(QThread):
    """Listen once, transcribe, report the text. Never acts on the desktop."""
    level = Signal(float)
    stage = Signal(str)
    heard = Signal(str)
    failed = Signal(str)

    def __init__(self, model_name="base.en", microphone=None, transcriber=None):
        super().__init__()
        self.stop_event = threading.Event()
        self.microphone = microphone or Microphone()
        self.transcriber = transcriber or Transcriber(model_name)

    def run(self):
        try:
            beep()  # an audible cue that Klicky is listening, for people who cannot see the popup
            self.stage.emit("listening")
            audio = self.microphone.record(self.stop_event, self.level.emit)
            self.stage.emit("transcribing")
            self.heard.emit(self.transcriber.transcribe(audio, self.stop_event))
        except Cancelled:
            self.stage.emit("stopped")
        except UserError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("Voice input stopped unexpectedly. You can type your question instead.")
