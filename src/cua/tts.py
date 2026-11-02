"""Read-aloud for answers: one utterance per step, a callback as each step starts, instant stop.

`ReadAloud.speak(lines, rate, on_line_start, on_end)` is the whole interface, so a cloud voice could replace the
Windows SAPI implementation later without touching the dock.
"""
import math
import os
import re
import threading
from queue import Queue, Empty
from PySide6.QtCore import QObject, Signal

SVSF_ASYNC, SVSF_PURGE, SVSF_NOT_XML = 1, 2, 16
GAP_MS = 250

KEY_WORDS = {"Ctrl": "Control", "Esc": "Escape", "PgDn": "Page Down", "PgUp": "Page Up", "Del": "Delete"}


def spoken(text):
    """How a step should sound: key names in words, no symbols, markdown or emoji."""
    text = re.sub(r"\s*\((?:\+|-)\)", "", text)  # "Plus (+)" is said as "Plus"
    for short, word in KEY_WORDS.items():
        text = re.sub(rf"\b{short}\b", word, text)
    text = re.sub(r"\bF(\d{1,2})\b", r"F \1", text)
    text = text.replace("+", " plus ").replace("&", " and ")
    text = re.sub(r"[*_#`~>|\[\]{}]", "", text)
    text = re.sub(r"[^\w\s.,;:!?'()\-]", "", text)  # drops emoji and arrows
    return re.sub(r"\s+", " ", text).strip()


def intro(answer):
    task = getattr(answer, "task", "") or ""
    if task:
        return f"Here's how to {task}."
    title = re.sub(r"\s*\(.*?\)", "", answer.title).strip()
    return f"Here's help with {title[0].lower() + title[1:]}." if title else "Here's how."


def sapi_rate(rate):
    """Speaking rate 0.5-1.5 (1.0 normal) to SAPI's -10..10 scale, where each step is roughly 10% faster."""
    return max(-10, min(10, round(math.log(max(.3, rate)) / math.log(1.1))))


def list_voices():
    """Installed Windows voices as (name, description)."""
    if os.name != "nt":
        return []
    try:
        import win32com.client
        voices = win32com.client.Dispatch("SAPI.SpVoice").GetVoices()
        return [voices.Item(i).GetDescription() for i in range(voices.Count)]
    except Exception:
        return []


class ReadAloud(QObject):
    # Carry the job's generation so a stopped job can never call back into a newer one.
    _line = Signal(int, int)
    _done = Signal(int)

    def __init__(self):
        super().__init__()
        self.voice_name = ""
        self.volume = 100
        self.speaking = False
        self.jobs = Queue()
        self.generation = 0
        self.callbacks = {}
        self.closed = False
        self.stop_signal = None
        if os.name == "nt":
            import win32event
            self.stop_signal = win32event.CreateEvent(None, False, False, None)
        self._line.connect(self._on_line)
        self._done.connect(self._on_done)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def speak(self, lines, rate=1.0, on_line_start=None, on_end=None):
        """Read lines in order. on_line_start(index) fires as each begins; on_end() only if read to the end."""
        self.stop()
        self.callbacks = {self.generation: (on_line_start, on_end)}
        self.jobs.put((self.generation, list(lines), rate))
        return self.generation

    def _on_line(self, generation, index):
        callback = self.callbacks.get(generation, (None, None))[0]
        if callback:
            callback(index)

    def _on_done(self, generation):
        callback = self.callbacks.pop(generation, (None, None))[1]
        if callback:
            callback()

    def stop(self):
        """Silence immediately and drop anything queued. A stopped job never calls on_end."""
        self.callbacks.clear()
        self.generation += 1
        if self.stop_signal:
            import win32event
            win32event.SetEvent(self.stop_signal)
        while True:
            try:
                self.jobs.get_nowait()
            except Empty:
                break

    def close(self):
        self.stop()
        self.closed = True

    def _run(self):
        if os.name != "nt":
            return
        import pythoncom
        pythoncom.CoInitialize()
        try:
            self._loop()
        finally:
            pythoncom.CoUninitialize()

    def _wait(self, handles, ms):
        import win32event
        result = win32event.WaitForMultipleObjects(handles, False, ms)
        return None if result == win32event.WAIT_TIMEOUT else result - win32event.WAIT_OBJECT_0

    def _loop(self):
        import win32com.client
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        chosen = None
        while not self.closed:
            try:
                generation, lines, rate = self.jobs.get(timeout=.1)
            except Empty:
                continue
            if generation != self.generation:
                continue
            if self.voice_name != chosen:
                voices = voice.GetVoices()
                for i in range(voices.Count):
                    if voices.Item(i).GetDescription() == self.voice_name:
                        voice.Voice = voices.Item(i)
                chosen = self.voice_name
            voice.Rate = sapi_rate(rate)
            completed = True
            self.speaking = True
            for index, line in enumerate(lines):
                if generation != self.generation:
                    completed = False
                    break
                self._line.emit(generation, index)
                voice.Volume = self.volume
                voice.Speak(line, SVSF_ASYNC | SVSF_PURGE | SVSF_NOT_XML)
                done = voice.SpeakCompleteEvent()
                while True:
                    woke = self._wait([done, self.stop_signal], 250)
                    if woke == 0:
                        break
                    if self.closed or generation != self.generation:
                        voice.Volume = 0  # mute first: buffered audio would otherwise play on
                        voice.Pause()
                        voice.Speak("", SVSF_ASYNC | SVSF_PURGE)
                        voice.Resume()
                        voice.WaitUntilDone(1000)
                        completed = False
                        break
                if not completed:
                    break
                if index < len(lines) - 1:
                    self._wait([self.stop_signal], GAP_MS)  # short pause between steps; Stop cuts it
                    if generation != self.generation:
                        completed = False
                        break
            self.speaking = False
            if completed:
                self._done.emit(generation)
