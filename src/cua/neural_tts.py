"""Natural read-aloud with Microsoft Edge's neural voices (the voices behind Edge's Read Aloud), via edge-tts.

Same interface as tts.ReadAloud: speak(lines, rate, on_line_start, on_end), stop(), close(). Each line's audio is
fetched while the previous one plays, and kept in a small disk cache, so only the first line of an answer waits for
the network. Needs internet; the text being read is sent to Microsoft. If a line can't be fetched in time (offline,
service changed), the rest of that answer is read by the Windows voice instead, so Klicky never goes silent.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import hashlib
import io
import os
from pathlib import Path
import threading
import time
from queue import Empty, Queue
import numpy as np
from PySide6.QtCore import QObject, Signal
from .tts import GAP_MS, ReadAloud

SAMPLE_RATE = 24000
FETCH_TIMEOUT_S = 6     # a line that isn't back by then is read by the Windows voice
BLOCK = 1200            # frames written per chunk: 50 ms, so Stop cuts in within about that
VOICES = {  # offered in Settings; any Edge voice name works
    "en-US-AvaNeural": "Ava (US)", "en-US-AndrewNeural": "Andrew (US)", "en-US-EmmaNeural": "Emma (US)",
    "en-GB-SoniaNeural": "Sonia (UK)", "en-IN-NeerjaNeural": "Neerja (Indian English)", "en-IN-PrabhatNeural": "Prabhat (Indian English)",
}


def edge_rate(rate):
    """Speaking rate 0.5-1.5 (1.0 normal) to edge-tts's "+10%" form."""
    return f"{round((rate - 1) * 100):+d}%"


def cache_dir():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Klicky" / "voice-cache"


def fetch_mp3(text, voice, rate):
    """MP3 bytes for one line from the Edge voice service (blocking)."""
    import edge_tts

    async def collect():
        audio = bytearray()
        async for message in edge_tts.Communicate(text, voice, rate=edge_rate(rate)).stream():
            if message["type"] == "audio":
                audio += message["data"]
        return bytes(audio)
    return asyncio.run(collect())


def decode(mp3):
    """MP3 bytes to mono float32 samples at SAMPLE_RATE."""
    import av
    with av.open(io.BytesIO(mp3)) as container:
        resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
        chunks = [out.to_ndarray().reshape(-1) for frame in container.decode(audio=0) for out in resampler.resample(frame)]
        chunks += [out.to_ndarray().reshape(-1) for out in resampler.resample(None)]
    return np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(0, np.float32)


class Synthesizer:
    """Line -> samples, from the disk cache or the service. Injected as a fake in tests."""
    def __init__(self, folder=None, fetch=fetch_mp3):
        self.folder, self.fetch = folder or cache_dir(), fetch

    def __call__(self, text, voice, rate):
        key = hashlib.sha1(f"{voice}|{edge_rate(rate)}|{text}".encode("utf-8")).hexdigest()
        path = self.folder / f"{key}.mp3"
        try:
            mp3 = path.read_bytes()
        except OSError:
            mp3 = self.fetch(text, voice, rate)
            if not mp3:
                raise RuntimeError("no audio")
            try:
                self.folder.mkdir(parents=True, exist_ok=True)
                path.write_bytes(mp3)
            except OSError:
                pass
        return decode(mp3)


def play(samples, stop, volume=1.0):
    """Play samples on the default output, returning False as soon as stop is set."""
    import sounddevice as sd
    with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
        for start in range(0, len(samples), BLOCK):
            if stop():
                return False
            stream.write((samples[start:start + BLOCK] * volume).reshape(-1, 1))
    return not stop()


class NeuralReadAloud(QObject):
    _line = Signal(int, int)
    _done = Signal(int)

    def __init__(self, synthesize=None, player=play, fallback=None):
        super().__init__()
        self.voice_name = ""                 # Windows voice, used when the natural voice can't be reached
        self.neural_voice = "en-US-AvaNeural"
        self.volume = 100
        self.speaking = False
        self.synthesize = synthesize or Synthesizer()
        self.player = player
        self.fallback = fallback or ReadAloud()
        self.jobs = Queue()
        self.generation = 0
        self.callbacks = {}
        self.closed = False
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="voice")
        self._line.connect(self._on_line)
        self._done.connect(self._on_done)
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def speak(self, lines, rate=1.0, on_line_start=None, on_end=None):
        """Read lines in order. on_line_start(index) fires as each begins; on_end() only if read to the end."""
        self.stop()
        self.callbacks = {self.generation: (on_line_start, on_end)}
        self.jobs.put((self.generation, list(lines), rate, self.neural_voice))
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
        self.fallback.stop()
        while True:
            try:
                self.jobs.get_nowait()
            except Empty:
                break

    def close(self):
        self.stop()
        self.closed = True
        self.fallback.close()
        self.pool.shutdown(wait=False, cancel_futures=True)
        if getattr(self, "warmer", None):
            self.warmer.shutdown(wait=False, cancel_futures=True)

    def prewarm(self, lines, rate=1.0):
        """Fetch lines Klicky says often (guide steps, intros) into the cache in the background, one at a time,
        so reading them later starts at once. Failures are ignored: those lines are fetched when needed."""
        if not hasattr(self, "warmer"):
            self.warmer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice-warm")
        voice = self.neural_voice

        def warm(line):
            if not self.closed:
                try:
                    self.synthesize(line, voice, rate)
                except Exception:
                    pass
        for line in dict.fromkeys(lines):
            self.warmer.submit(warm, line)

    def _hand_over(self, generation, lines, start, rate):
        """The natural voice is unreachable: the Windows voice reads the rest, with the same callbacks."""
        on_line, on_end = self.callbacks.get(generation, (None, None))
        if generation != self.generation:
            return
        self.fallback.voice_name, self.fallback.volume = self.voice_name, self.volume
        self.fallback.speak(lines[start:], rate, on_line_start=(lambda i: on_line(start + i)) if on_line else None,
                            on_end=on_end)

    def _loop(self):
        while not self.closed:
            try:
                generation, lines, rate, voice = self.jobs.get(timeout=.1)
            except Empty:
                continue
            if generation != self.generation:
                continue
            stopped = lambda generation=generation: self.closed or generation != self.generation
            # Ask for every line now; the pool fetches the next while the current one plays.
            futures = [self.pool.submit(self.synthesize, line, voice, rate) for line in lines]
            completed, self.speaking = True, True
            for index, future in enumerate(futures):
                samples, deadline = None, time.monotonic() + FETCH_TIMEOUT_S
                while samples is None and not stopped() and time.monotonic() < deadline:
                    try:
                        samples = future.result(timeout=.1)
                    except FutureTimeout:
                        continue
                    except Exception:
                        break
                if stopped():
                    completed = False
                    break
                if samples is None:  # offline or the service failed: the Windows voice carries on from here
                    completed = False
                    self.speaking = False
                    for rest in futures[index:]:
                        rest.cancel()
                    self._hand_over(generation, lines, index, rate)
                    break
                self._line.emit(generation, index)
                if not self.player(samples, stopped, self.volume / 100):
                    completed = False
                    break
                if index < len(lines) - 1:  # short pause between steps; Stop cuts it
                    pause_until = time.monotonic() + GAP_MS / 1000
                    while time.monotonic() < pause_until and not stopped():
                        time.sleep(.02)
            self.speaking = False
            if completed and not stopped():
                self._done.emit(generation)
