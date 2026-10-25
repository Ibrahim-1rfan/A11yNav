"""Real Qt widgets wired to fake controllers; no desktop input is generated."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import threading
import time
from PySide6.QtWidgets import QApplication
from cua.ui import MainWindow,TaskWorker
from cua.config import Settings
from cua.speech import Speaker


def test_ui_worker_and_stop(monkeypatch):
    app=QApplication.instance() or QApplication([])
    window=MainWindow(Settings())
    class FakeController:
        def __init__(self,emit): self.emit=emit
        def run(self,text,stop):
            self.emit("processing","Test task running")
            stop.wait(2)
            self.emit("inactive","Task stopped")
            return "stopped"
    window.worker=TaskWorker(Settings(),"Search for test",FakeController)
    window.worker.status.connect(window.update_status)
    window.worker.finished.connect(window.task_finished)
    window.set_running(True); window.worker.start()
    deadline=time.monotonic()+2
    while "running" not in window.status_label.text() and time.monotonic()<deadline:
        app.processEvents(); time.sleep(.01)
    window.stop.click()
    assert window.worker.stop_event.is_set()
    assert window.worker.wait(1000)
    app.processEvents()
    assert window.status_label.text() == "Task stopped"
    assert window.start.isEnabled()
    window.close()


def test_speech_toggle_purges_queue():
    speaker=Speaker()
    speaker.say("Should be silent")
    assert speaker.queue.empty()
    speaker.set_enabled(True)
    assert speaker.enabled
    speaker.set_enabled(False)
    assert not speaker.enabled and speaker.queue.empty()
    speaker.close(); speaker.thread.join(1)


def test_settings_exposes_task_budget_and_image_controls():
    from cua.ui import SetupDialog
    app=QApplication.instance() or QApplication([])
    dialog=SetupDialog(Settings(),None)
    dialog.timeout.setValue(120)
    assert "510 seconds" in dialog.budget_note.text()
    dialog.task_timeout.setValue(600)
    dialog.image_edge.setValue(960)
    dialog.tokens.setValue(256)
    dialog.adapter.setCurrentText("json")
    saved=dialog.values()
    assert (saved.task_timeout,saved.max_image_edge,saved.max_tokens,saved.adapter)==(600,960,256,"json")
    assert "may cut off" not in dialog.budget_note.text()
    dialog.close()
