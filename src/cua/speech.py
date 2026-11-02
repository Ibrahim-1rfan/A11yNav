"""Optional local TTS on its own thread; Stop cuts off speech within about 50 ms and purges queued feedback."""
from queue import Queue, Empty
import threading
import os
import time

SVSF_ASYNC, SVSF_PURGE, SVSF_NOT_XML = 1, 2, 16


class Speaker:
    def __init__(self, error=lambda message: None):
        self.voice = None
        self.volume = 100
        self.speaking, self.stopped_cleanly, self.cut_at = False, None, None
        self.stop_signal = None
        if os.name == "nt":
            import win32event
            # Auto-reset event: wakes the speech thread instantly when Stop is pressed.
            self.stop_signal = win32event.CreateEvent(None, False, False, None)
        self.enabled = False
        self.queue = Queue(maxsize=3)
        self.error = error
        self.generation = 0
        self.closed = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.stop()

    def stop(self):
        """Cut off current speech and drop anything queued."""
        self.generation += 1
        if self.stop_signal:
            import win32event
            win32event.SetEvent(self.stop_signal)
        while True:
            try:
                self.queue.get_nowait()
            except Empty:
                break

    def say(self, message, force=False):
        """force speaks even with spoken feedback off, e.g. answering a question the user asked by voice."""
        if (self.enabled or force) and not self.queue.full():
            self.queue.put((self.generation, message, force))

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

    @staticmethod
    def _wait(handles, milliseconds):
        """Index of the handle that fired, or None on timeout."""
        import win32event
        result = win32event.WaitForMultipleObjects(handles, False, milliseconds)
        return None if result == win32event.WAIT_TIMEOUT else result - win32event.WAIT_OBJECT_0

    def _speak_loop(self):
        # Windows SAPI directly: pyttsx3 reports "not busy" while SAPI is still talking, so it could not be
        # interrupted. Here every 50 ms of speech re-checks for Stop and purges the voice at once.
        voice = None
        while not self.closed:
            try:
                generation, message, force = self.queue.get(timeout=.1)
            except Empty:
                continue
            if not (self.enabled or force) or generation != self.generation:
                continue
            try:
                if voice is None:
                    import win32com.client
                    voice = win32com.client.Dispatch("SAPI.SpVoice")
                    voice.Rate = 1
                    self.voice = voice
                voice.Volume = self.volume
                # Plain text only: guide text is never interpreted as SAPI markup.
                voice.Speak(message, SVSF_ASYNC | SVSF_PURGE | SVSF_NOT_XML)
                self.speaking = True
                done = voice.SpeakCompleteEvent()
                while True:
                    # Wake the moment speech ends or Stop is pressed, not on a polling tick.
                    woke = self._wait([done, self.stop_signal], 250)
                    if woke == 0:
                        break
                    if self.closed or not (self.enabled or force) or generation != self.generation:
                        # Mute first: audio already handed to the sound card would otherwise play on.
                        voice.Volume = 0
                        self.cut_at = time.monotonic()
                        voice.Pause()
                        voice.Speak("", SVSF_ASYNC | SVSF_PURGE)
                        voice.Resume()
                        self.stopped_cleanly = bool(voice.WaitUntilDone(1000))
                        break
                self.speaking = False
            except Exception:
                self.speaking = False
                self.enabled = False
                self.error("Voice feedback is unavailable. Written status remains available.")
