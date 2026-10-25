"""Optional local TTS on its own thread; mute purges queued feedback."""
from queue import Queue, Empty
import threading
import os


class Speaker:
    def __init__(self, error=lambda message: None):
        self.enabled = False
        self.queue = Queue(maxsize=3)
        self.error = error
        self.generation = 0
        self.closed = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.generation += 1
        while True:
            try:
                self.queue.get_nowait()
            except Empty:
                break

    def say(self, message):
        if self.enabled and not self.queue.full():
            self.queue.put((self.generation, message))

    def close(self):
        self.set_enabled(False)
        self.closed = True

    def _run(self):
        if os.name == "nt":
            import pythoncom
            pythoncom.CoInitialize()
        try:
            self._speak_loop()
        finally:
            if os.name == "nt":
                pythoncom.CoUninitialize()

    def _speak_loop(self):
        engine = None
        while not self.closed:
            try:
                generation, message = self.queue.get(timeout=.1)
            except Empty:
                continue
            if not self.enabled or generation != self.generation:
                continue
            try:
                if engine is None:
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.setProperty("rate", 170)
                engine.say(message)
                engine.startLoop(False)
                while engine.isBusy():
                    if not self.enabled or generation != self.generation:
                        engine.stop()
                    engine.iterate()
                    threading.Event().wait(.02)
                engine.endLoop()
            except Exception:
                self.enabled = False
                self.error("Voice feedback is unavailable. Written status remains available.")
