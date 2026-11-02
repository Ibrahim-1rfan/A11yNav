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


def wait_for(app, condition, seconds=3):
    deadline=time.monotonic()+seconds
    while not condition() and time.monotonic()<deadline:
        app.processEvents(); time.sleep(.01)
    return condition()


def test_question_shows_answer_and_cognitive_stepping(monkeypatch):
    from dataclasses import replace
    from cua.assistant import Answer
    monkeypatch.setattr("cua.ui.save",lambda settings: None)
    app=QApplication.instance() or QApplication([])
    window=MainWindow(replace(Settings(),profile="cognitive"))
    answer=Answer("Make pages bigger",("edge",),("Press Ctrl and Plus.","Press Ctrl and 0 to reset."),("https://support.microsoft.com/x",),True)
    class Helper:
        def answer(self,question,stop): return answer
    window.ask("How do I zoom in Edge?",Helper)
    assert wait_for(app,lambda: window.answer is not None and not window.worker.isRunning())
    app.processEvents()
    assert window.status_label.text()=="Here is how to do it." and window.start.isEnabled()
    assert "Step 1 of 2" in window.answer_view.toPlainText() and not window.step_controls.isHidden()
    assert not window.back.isEnabled() and window.next.isEnabled()
    window.next.click()
    assert "Press Ctrl and 0" in window.answer_view.toPlainText() and not window.next.isEnabled()
    assert window.compact.badge.text()=="Done"
    window.close()


def test_question_stop_and_default_profile_lists_all_steps(monkeypatch):
    from cua.assistant import Answer
    from cua.models import Cancelled
    app=QApplication.instance() or QApplication([])
    window=MainWindow(Settings())
    class Slow:
        def answer(self,question,stop):
            stop.wait(2)
            raise Cancelled()
    window.ask("How do I zoom?",Slow)
    assert wait_for(app,lambda: window.worker.isRunning())
    window.stop.click()
    assert window.worker.wait(1000)
    app.processEvents()
    assert window.status_label.text()=="Question stopped" and window.answer_view.isHidden()
    window.show_answer(Answer("T",("chrome",),("One.","Two.","Three."),(),True))
    assert window.step_controls.isHidden() and "Three." in window.answer_view.toPlainText()
    window.close()


def test_profile_switch_restyles_and_saves(monkeypatch):
    saved=[]
    monkeypatch.setattr("cua.ui.save",saved.append)
    app=QApplication.instance() or QApplication([])
    window=MainWindow(Settings())
    window.profile_box.setCurrentIndex(window.profile_box.findData("low_vision"))
    assert window.settings.profile=="low_vision" and window.settings.font_px==30 and window.voice.isChecked()
    assert saved[-1].profile=="low_vision"
    assert "#ffe600" in app.styleSheet() and "border:5px" in app.styleSheet()
    assert window.compact.width()>=30*17
    window.profile_box.setCurrentIndex(window.profile_box.findData("motor"))
    assert "Enter starts" in window.voice_note.text()
    window.close()


def test_settings_dialog_adopts_profile_and_rag_fields():
    from cua.ui import SetupDialog
    app=QApplication.instance() or QApplication([])
    dialog=SetupDialog(Settings(),None)
    dialog.profile.setCurrentIndex(dialog.profile.findData("cognitive"))
    assert dialog.size.value()==20
    dialog.text_model.setText(" qwen2.5-3b-instruct ")
    dialog.rag_app.setCurrentText("firefox")
    saved=dialog.values()
    assert (saved.profile,saved.text_model,saved.rag_app,saved.font_px)==("cognitive","qwen2.5-3b-instruct","firefox",20)
    dialog.close()


def test_hotkey_summon_uses_the_browser_the_user_was_in(monkeypatch):
    from cua.assistant import Answer
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr("cua.ui.foreground_app",lambda: (12345,"chrome"))
    window=MainWindow(Settings(hotkey=""))
    window.summon()
    assert window.context_app=="chrome" and window.return_hwnd==12345
    assert "Ask about Chrome" in window.status_label.text() and window.isVisible()
    class Helper:
        def answer(self,question,stop): return Answer("T",("chrome",),("One.",),(),True)
    window.ask("How do I zoom in?",Helper)
    assert window.worker.settings.rag_app=="chrome"
    assert wait_for(app,lambda: not window.worker.isRunning())
    window.ask("How do I zoom in Firefox?",Helper)
    assert window.worker.settings.rag_app=="auto"  # a browser named in the question wins
    assert wait_for(app,lambda: not window.worker.isRunning())
    focused=[]
    monkeypatch.setattr("cua.ui.ctypes.windll.user32.SetForegroundWindow",focused.append)
    window.escape_pressed()
    assert focused==[12345] and window.context_app is None and not window.isVisible()
    window.close()


def test_hotkey_conflict_is_reported(monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr("cua.ui.GlobalHotkey.register",lambda self,text: False)
    window=MainWindow(Settings())
    assert "already used by another app" in window.voice_note.text()
    window.close()


def test_only_the_default_hotkey_falls_back(monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr("cua.ui.GlobalHotkey.register",lambda self,text: text=="Win+Shift+K")
    window=MainWindow(Settings())
    assert window.active_hotkey=="Win+Shift+K" and "Press Win+Shift+K" in window.voice_note.text()
    window.close()
    custom=MainWindow(Settings(hotkey="Ctrl+Alt+J"))
    assert custom.active_hotkey=="" and "Ctrl+Alt+J is already used" in custom.voice_note.text()
    custom.close()
