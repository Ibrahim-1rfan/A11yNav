"""Voice input: microphone capture with automatic end-of-speech detection, then Whisper.

Audio stays in memory: it is never written to disk or logged. With Settings > Speech to text on "auto" and a
GROQ_API_KEY in keys.env, the finished question's clip is sent to Groq's hosted Whisper large (more accurate, fast);
live captions and any failed call use on-device Whisper. "local" never sends audio anywhere.
"""
from dataclasses import dataclass
import os
import threading
from PySide6.QtCore import QThread, Signal
from .config import UserError, settings_path
from .models import Cancelled

RATE = 16000
CHUNK_MS = 50
CHUNK = RATE * CHUNK_MS // 1000  # 50 ms: fine enough for the orb to follow the voice smoothly
# Primes Whisper with the words Klicky's questions use, so "Chrome" is not heard as "crow".
VOCABULARY = ("Questions about the IBA LMS: course outline, Syllabus, Resources, lecture slides, Assignments, submit, "
              "Drop Box, Tests & Quizzes, Announcements, Calendar, HCI. And about the web browsers Chrome, Edge and "
              "Firefox: zoom, text size, reader mode, read aloud, dark mode, captions, tabs, bookmarks, favorites, history.")
MODELS = {"tiny.en": "Systran/faster-whisper-tiny.en", "base.en": "Systran/faster-whisper-base.en",
          "small.en": "Systran/faster-whisper-small.en"}
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"
GROQ_TIMEOUT_S = 8
FILLERS = {"thank you", "thanks", "you", "bye", "thanks for watching"}
NO_MIC = "I can't use the microphone. Check that one is connected and that Windows Settings > Privacy > Microphone allows desktop apps. You can type instead."


def model_dir(name):
    return settings_path().parent / "models" / f"faster-whisper-{name}"


def model_installed(name):
    path = model_dir(name)
    return (path / "model.bin").exists() and (path / "config.json").exists()


@dataclass
class Endpointer:
    """Decides when speech started and ended from short loudness readings.

    The first readings set a noise floor; speech is anything clearly above it. Listening ends after a
    pause following speech, at a hard length limit, or when nobody speaks at all.
    """
    chunk_ms: int = CHUNK_MS
    pause_ms: int = 1200       # 1.2 s of quiet after speech ends the question
    max_ms: int = 120000       # only a safety net (a noisy room never "pauses"): the pause is what ends a question
    no_speech_ms: int = 7000   # give up when nobody speaks
    floor_ms: int = 150
    min_level: float = .012

    def __post_init__(self):
        self.levels, self.speech_chunks, self.quiet = [], 0, 0
        n = lambda ms: max(1, round(ms / self.chunk_ms))
        self.pause_chunks, self.max_chunks = n(self.pause_ms), n(self.max_ms)
        self.no_speech_chunks, self.floor_chunks = n(self.no_speech_ms), n(self.floor_ms)
        self.min_speech = n(100)  # a single click is not speech

    @property
    def threshold(self):
        floor = sorted(self.levels[:self.floor_chunks])[len(self.levels[:self.floor_chunks]) // 2] if self.levels else 0
        return max(self.min_level, floor * 3)

    @property
    def speaking(self):
        return self.speech_chunks >= self.min_speech

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
        if self.speaking and self.quiet >= self.pause_chunks:
            return "done"
        if len(self.levels) >= self.max_chunks:
            return "limit" if self.speaking else "no_speech"
        if not self.speech_chunks and len(self.levels) >= self.no_speech_chunks:
            return "no_speech"
        return None


class Microphone:
    """Records one spoken question from the default input device."""
    def record(self, stop, on_level, on_chunk=None, endpointer=None):
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
                    if on_chunk:
                        on_chunk(mono)
                    level = float(np.sqrt(np.mean(mono * mono)))
                    on_level(level)  # raw RMS; the orb scales and smooths it
                    result = endpointer.feed(level)
                    if result == "no_speech":
                        raise UserError("Couldn't hear that. Tap the orb to try again, or start typing.")
                    if result:
                        return np.concatenate(chunks)
        except sd.PortAudioError as exc:
            raise UserError(NO_MIC) from exc


class Transcriber:
    """On-device Whisper. The model loads once and is reused; one inference runs at a time."""
    _lock = threading.Lock()
    _infer = threading.Lock()
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

    def _text(self, audio, **options):
        model = self._model()
        with self._infer:
            segments, _ = model.transcribe(audio, language="en", initial_prompt=VOCABULARY, condition_on_previous_text=False,
                                           without_timestamps=True, **options)
            return " ".join(segment.text.strip() for segment in segments).strip()

    def partial(self, audio):
        """Quick, rough transcript of the words so far, for live captions only."""
        text = self._text(audio, beam_size=1, vad_filter=False)
        return "" if text.lower().strip(" .!?") in FILLERS else text

    def transcribe(self, audio, stop):
        if stop.is_set():
            raise Cancelled()
        text = self._text(audio, beam_size=5, vad_filter=True)
        if stop.is_set():
            raise Cancelled()
        return heard(text)


def heard(text):
    # Whisper can invent a polite filler on near-silence; treat that as nothing heard.
    if not text or text.lower().strip(" .!?") in FILLERS:
        raise UserError("Couldn't hear that. Tap the orb to try again, or start typing.")
    return text


def hosted(settings):
    """True when the finished question goes to Groq's hosted Whisper."""
    return getattr(settings, "speech_service", "auto") == "auto" and bool(os.environ.get("GROQ_API_KEY"))


def wav_bytes(audio):
    """16 kHz mono 16-bit WAV, in memory only."""
    import io
    import wave
    import numpy as np
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
    return out.getvalue()


class HostedTranscriber:
    """Groq's Whisper large for the finished question; on-device Whisper for live captions and as the fallback."""

    def __init__(self, local, post=None):
        self.local, self.post = local, post
        self.used = ""  # which engine heard the last question, for the step log

    def partial(self, audio):
        return self.local.partial(audio) if model_installed(self.local.name) else ""

    def ask_groq(self, audio):
        import requests
        response = (self.post or requests.post)(
            GROQ_URL, headers={"Authorization": f"Bearer {os.environ.get('GROQ_API_KEY', '')}"},
            files={"file": ("question.wav", wav_bytes(audio), "audio/wav")},
            data={"model": GROQ_MODEL, "language": "en", "temperature": "0", "response_format": "json", "prompt": VOCABULARY},
            timeout=GROQ_TIMEOUT_S, allow_redirects=False)
        response.raise_for_status()
        return " ".join(str(response.json().get("text", "")).split())

    def transcribe(self, audio, stop):
        if stop.is_set():
            raise Cancelled()
        try:
            text = self.ask_groq(audio)
            self.used = "groq"
        except Exception as exc:
            self.used = f"local (groq failed: {type(exc).__name__})"
            if not model_installed(self.local.name):
                raise UserError("I couldn't reach the speech service. Check the internet, or type your question.")
            return self.local.transcribe(audio, stop)
        if stop.is_set():
            raise Cancelled()
        return heard(text)


def transcriber_for(settings, post=None):
    local = Transcriber(settings.voice_model)
    return HostedTranscriber(local, post) if hosted(settings) else local


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
    """Listen once with live captions, transcribe, report the text. Never acts on the desktop."""
    level = Signal(float)
    stage = Signal(str)
    partial = Signal(str)
    heard = Signal(str)
    failed = Signal(str)

    def __init__(self, model_name="base.en", microphone=None, transcriber=None, cue=True):
        super().__init__()
        self.stop_event = threading.Event()
        self.microphone = microphone or Microphone()
        self.transcriber = transcriber or Transcriber(model_name)  # or transcriber_for(settings): Groq when chosen
        self.cue = cue

    def run(self):
        recorded = threading.Event()
        buffer, endpointer = [], Endpointer()

        def captions():
            # Re-transcribe the words so far about once a second while the person talks.
            import numpy as np
            seen = 0
            while not recorded.wait(.9):
                if not endpointer.speaking or len(buffer) == seen:
                    continue
                seen = len(buffer)
                try:
                    text = self.transcriber.partial(np.concatenate(buffer[:seen])[-RATE * 12:])
                except Exception:
                    continue
                if text and not recorded.is_set():
                    self.partial.emit(text)

        try:
            if self.cue:
                beep()  # an audible cue that Klicky is listening, for people who cannot see the dock
            self.stage.emit("listening")
            threading.Thread(target=captions, daemon=True).start()
            audio = self.microphone.record(self.stop_event, self.level.emit, on_chunk=buffer.append, endpointer=endpointer)
            recorded.set()
            self.stage.emit("transcribing")
            text = self.transcriber.transcribe(audio, self.stop_event)
            log_heard(audio, endpointer, getattr(self.transcriber, "used", "") or "local")
            self.heard.emit(text)
        except Cancelled:
            self.stage.emit("stopped")
        except UserError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("Voice input stopped unexpectedly. You can type your question instead.")
        finally:
            recorded.set()


def log_heard(audio, endpointer, engine):
    """One line per voice question in klicky.log: length, loudness and engine. Never the audio or the words."""
    import logging
    try:
        import numpy as np
        levels = sorted(endpointer.levels) or [0.0]
        voice_level = levels[int(len(levels) * .9)] if len(levels) > 1 else levels[0]
        logging.getLogger("klicky.walk").info(
            "voice question: %.1f s, room %.4f, voice %.4f, peak %.2f, heard by %s",
            len(audio) / RATE, endpointer.threshold / 3, voice_level, float(np.max(np.abs(audio))) if len(audio) else 0.0, engine)
    except Exception:
        pass


class BargeInMonitor(QThread):
    """Listens while Klicky reads an answer and reports when the person starts talking over it.

    There is no echo cancellation on a desktop, so Klicky's own voice reaches the microphone. The first
    0.6 s learn how loud that echo is; only sound well above it, held for 300 ms, counts as the person.
    """
    barged = Signal()

    def __init__(self, learn_ms=600, hold_ms=300, factor=2.5, min_level=.03):
        super().__init__()
        self.stop_event = threading.Event()
        self.learn = max(1, learn_ms // CHUNK_MS)
        self.hold = max(1, hold_ms // CHUNK_MS)
        self.factor, self.min_level = factor, min_level

    def decide(self, levels):
        """Given loudness readings so far, True once the person is talking over the answer."""
        if len(levels) <= self.learn:
            return False
        baseline = sorted(levels[:self.learn])[int(self.learn * .9) - 1 if self.learn > 1 else 0]
        threshold = max(self.min_level, baseline * self.factor)
        recent = levels[-self.hold:]
        return len(recent) == self.hold and all(level >= threshold for level in recent)

    def run(self):
        try:
            import numpy as np
            import sounddevice as sd
            levels = []
            with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=CHUNK) as stream:
                while not self.stop_event.is_set():
                    data, _ = stream.read(CHUNK)
                    mono = data[:, 0]
                    levels.append(float(np.sqrt(np.mean(mono * mono))))
                    if self.decide(levels):
                        self.barged.emit()
                        return
        except Exception:
            return  # barge-in is a convenience; Esc and the orb still stop reading
