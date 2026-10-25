"""Accessible Qt interface, persistent stop widget and first-run model settings."""
from dataclasses import replace
import threading
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QCheckBox, QDialog, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QDialogButtonBox, QMessageBox, QScrollArea)
from .config import Settings, UserError, save
from .models import LocalModel
from .browser import WindowsBrowser
from .controller import Controller
from .perception import ScreenCapture
from .speech import Speaker

COLORS = {"inactive": "#a9bbc6", "processing": "#ffcf70", "action": "#57dbe0", "success": "#68e3b5", "error": "#ffadad"}
LABELS = {"inactive": "READY", "processing": "LOOKING", "action": "WORKING", "success": "DONE", "error": "NEEDS HELP"}


def selected_font():
    available = QFontDatabase.families()
    return next((name for name in ("Intel One Mono", "IntelOne Mono", "Consolas", "DejaVu Sans Mono") if name in available), QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family())


class TaskWorker(QThread):
    status = Signal(str, str)
    outcome = Signal(str)

    def __init__(self, settings, text, factory=None):
        super().__init__()
        self.settings, self.text = settings, text
        self.stop_event = threading.Event()
        self.factory = factory

    def run(self):
        import pythoncom
        pythoncom.CoInitialize()
        try:
            if self.factory:
                controller = self.factory(self.status.emit)
            else:
                controller = Controller(self.settings, LocalModel(self.settings), ScreenCapture(), WindowsBrowser(self.settings.browser), self.status.emit)
            self.outcome.emit(controller.run(self.text, self.stop_event))
        except Exception:
            self.status.emit("error", "The task could not start. Check your Windows setup and try again.")
            self.outcome.emit("error")
        finally:
            pythoncom.CoUninitialize()


class CheckWorker(QThread):
    result = Signal(bool, str)
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
    def run(self):
        try:
            LocalModel(self.settings).health(threading.Event())
            self.result.emit(True, "Server and model found. Image capability is checked during your task.")
        except UserError as exc:
            self.result.emit(False, str(exc))


class SetupDialog(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.setWindowTitle("Klicky settings")
        self.resize(690, 640)
        self.settings = settings
        self.check_worker = None
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        intro = QLabel("1. Load a vision model and its projector in LM Studio.\n2. Start the local server in its Developer tab.\n3. Copy the exact model identifier below.\nUse ui_tars for UI-TARS, or json for Qwen2.5-VL.\nThe search needs at least four model replies. Allow enough time for the whole task.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.endpoint, self.model = QLineEdit(settings.endpoint), QLineEdit(settings.model)
        self.adapter, self.browser, self.engine = QComboBox(), QComboBox(), QComboBox()
        for combo, values, current in [(self.adapter, ["ui_tars", "json"], settings.adapter), (self.browser, ["default", "edge", "chrome", "firefox"], settings.browser), (self.engine, ["bing", "google", "duckduckgo"], settings.engine)]:
            combo.addItems(values)
            combo.setCurrentText(current)
        self.size, self.limit, self.timeout = QSpinBox(), QSpinBox(), QSpinBox()
        self.task_timeout, self.image_edge, self.tokens = QSpinBox(), QSpinBox(), QSpinBox()
        for control, lo, hi, value in [(self.size,16,28,settings.font_px),(self.limit,3,30,settings.max_actions),(self.timeout,1,120,int(settings.request_timeout)),(self.task_timeout,10,600,int(settings.task_timeout)),(self.image_edge,640,1920,settings.max_image_edge),(self.tokens,128,2048,settings.max_tokens)]:
            control.setRange(lo,hi)
            control.setValue(value)
        for label, control in [("Local server",self.endpoint),("Model identifier",self.model),("Model adapter",self.adapter),("Browser preference",self.browser),("Search engine",self.engine),("Text size",self.size),("Action limit",self.limit),("Model timeout in seconds",self.timeout),("Whole-task limit in seconds",self.task_timeout),("Image longest edge in pixels",self.image_edge),("Maximum reply tokens",self.tokens)]:
            control.setAccessibleName(label)
            form.addRow(label,control)
        layout.addLayout(form)
        self.budget_note = QLabel()
        self.budget_note.setWordWrap(True)
        layout.addWidget(self.budget_note)
        self.timeout.valueChanged.connect(self.update_budget_note)
        self.task_timeout.valueChanged.connect(self.update_budget_note)
        self.update_budget_note()
        self.check = QPushButton("Check connection")
        self.check.clicked.connect(self.check_connection)
        layout.addWidget(self.check)
        self.message = QLabel("Only local model servers are supported. Search topics still go to the chosen search engine.")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.commit)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

    def values(self):
        return replace(self.settings, endpoint=self.endpoint.text().strip(), model=self.model.text().strip(), adapter=self.adapter.currentText(), browser=self.browser.currentText(), engine=self.engine.currentText(), font_px=self.size.value(), max_actions=self.limit.value(), request_timeout=self.timeout.value(), task_timeout=self.task_timeout.value(), max_image_edge=self.image_edge.value(), max_tokens=self.tokens.value()).validate()

    def update_budget_note(self):
        suggested = 4 * self.timeout.value() + 30
        self.budget_note.setText(
            f"The whole-task limit may cut off four slow replies. Allow at least {suggested} seconds at this model timeout. Smaller images reduce image-processing work but may make text harder to read."
            if self.task_timeout.value() < suggested else
            "Time is allowed for four model replies plus browser setup. Extra waits and retries also use this budget. Smaller images can help on slower machines.")

    def check_connection(self):
        try:
            settings = self.values()
        except UserError as exc:
            self.message.setText(str(exc))
            return
        self.check.setEnabled(False)
        self.buttons.setEnabled(False)
        self.message.setText("Checking the local server...")
        self.check_worker = CheckWorker(settings)
        self.check_worker.result.connect(lambda ok, message: self.message.setText(message))
        self.check_worker.finished.connect(lambda: (self.check.setEnabled(True), self.buttons.setEnabled(True)))
        self.check_worker.start()

    def reject(self):
        if self.check_worker and self.check_worker.isRunning():
            return
        super().reject()

    def closeEvent(self, event):
        if self.check_worker and self.check_worker.isRunning():
            event.ignore()
        else:
            super().closeEvent(event)

    def commit(self):
        try:
            self.settings = self.values()
            save(self.settings)
            self.accept()
        except (UserError, OSError) as exc:
            self.message.setText(str(exc) if isinstance(exc, UserError) else "Settings could not be saved. Check folder permissions.")


class CompactWidget(QWidget):
    stop = Signal()
    expand = Signal()
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Klicky controls")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        self.badge = QLabel("READY")
        self.badge.setAccessibleName("Agent state")
        self.badge.setStyleSheet("border:3px solid #68e3b5; border-radius:14px; padding:8px;")
        self.message = QLabel("Ready for your command")
        self.message.setWordWrap(True)
        layout.addWidget(self.badge)
        layout.addWidget(self.message)
        row = QHBoxLayout()
        self.open_button, self.stop_button = QPushButton("Open"), QPushButton("Stop")
        self.open_button.clicked.connect(self.expand)
        self.stop_button.clicked.connect(self.stop)
        self.stop_button.setEnabled(False)
        row.addWidget(self.open_button)
        row.addWidget(self.stop_button)
        layout.addLayout(row)
        geometry = QApplication.primaryScreen().availableGeometry()
        self.move(geometry.right()-360, geometry.bottom()-290)

    def closeEvent(self, event):
        # The always-available entry point remains until the main app is closed.
        event.ignore()
        self.expand.emit()

    def status(self, state, message):
        self.badge.setText(LABELS[state])
        self.badge.setStyleSheet(f"border:3px solid {COLORS[state]}; color:{COLORS[state]}; border-radius:14px; padding:8px;")
        self.message.setText(message)


class MainWindow(QWidget):
    speech_error = Signal(str)
    def __init__(self, settings: Settings, startup_error=""):
        super().__init__()
        self.settings = settings
        self.worker = None
        self.setWindowTitle("Klicky | Accessible browser assistant")
        self.resize(760, 700)
        self.compact = CompactWidget()
        self.compact.stop.connect(self.stop_task)
        self.compact.expand.connect(self.expand)
        self.speaker = Speaker(self.speech_error.emit)
        self.speech_error.connect(lambda msg: self.voice_note.setText(msg))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28,24,28,24)
        layout.setSpacing(14)
        title = QLabel("Klicky")
        title.setStyleSheet("font-size:32px; font-weight:bold; color:#68e3b5;")
        layout.addWidget(title)
        subtitle = QLabel("A little help finding your way.")
        layout.addWidget(subtitle)
        prompt_label = QLabel("What would you like to search for?")
        layout.addWidget(prompt_label)
        self.input = QTextEdit()
        self.input.setAccessibleName("Search task")
        self.input.setPlaceholderText("Open my browser and search for accessible computer interfaces")
        self.input.setMinimumHeight(130)
        self.input.setTabChangesFocus(True)
        prompt_label.setBuddy(self.input)
        layout.addWidget(self.input)
        self.example = QPushButton("Try: Search for accessible computer interfaces")
        self.example.clicked.connect(lambda: self.input.setPlainText("Search for accessible computer interfaces"))
        layout.addWidget(self.example)
        row = QHBoxLayout()
        self.start, self.stop = QPushButton("Start search"), QPushButton("Stop")
        self.start.setShortcut("Alt+S")
        self.stop.setShortcut("Alt+X")
        self.start.setStyleSheet("background:#68e3b5; color:#0a202b; font-weight:bold;")
        self.stop.setEnabled(False)
        self.start.clicked.connect(self.start_task)
        self.stop.clicked.connect(self.stop_task)
        row.addWidget(self.start)
        row.addWidget(self.stop)
        layout.addLayout(row)
        self.status_label = QLabel("Ready for your command")
        self.status_label.setWordWrap(True)
        self.status_label.setAccessibleName("Task status")
        layout.addWidget(self.status_label)
        self.privacy = QLabel("When you press Start, Klicky opens a search tab and sends browser screenshots to your local model. Keep private information out of view. Search topics go to your chosen search engine.")
        self.privacy.setWordWrap(True)
        self.privacy.setStyleSheet("color:#b8cbd4;")
        layout.addWidget(self.privacy)
        options = QHBoxLayout()
        self.voice = QCheckBox("Spoken feedback")
        self.voice.setChecked(settings.speech)
        self.voice.toggled.connect(self.toggle_speech)
        self.speaker.set_enabled(settings.speech)
        self.settings_button, self.compact_button = QPushButton("Settings"), QPushButton("Use small widget")
        self.settings_button.clicked.connect(self.open_settings)
        self.compact_button.clicked.connect(self.collapse)
        options.addWidget(self.voice)
        options.addWidget(self.settings_button)
        options.addWidget(self.compact_button)
        layout.addLayout(options)
        self.voice_note = QLabel("Keyboard: Alt+S starts. Alt+X stops while this window is focused.")
        self.voice_note.setWordWrap(True)
        layout.addWidget(self.voice_note)
        self.escape_shortcut = QShortcut(QKeySequence("Escape"),self)
        self.escape_shortcut.activated.connect(self.stop_task)
        self.apply_style()
        self.compact.show()
        if startup_error:
            self.update_status("error", startup_error)

    def apply_style(self):
        font = QFont(selected_font())
        font.setPixelSize(self.settings.font_px)
        QApplication.instance().setFont(font)
        QApplication.instance().setStyleSheet("QWidget { background:#0b202b; color:#f2f7f9; } QPushButton,QComboBox,QSpinBox,QLineEdit { padding:10px; border:1px solid #54717e; border-radius:7px; } QPushButton:focus,QTextEdit:focus,QLineEdit:focus,QComboBox:focus { border:3px solid #ffcf70; } QPushButton:disabled { color:#8298a2; background:#203743; } QTextEdit { background:#15323f; border:2px solid #54717e; border-radius:8px; padding:12px; } QCheckBox { spacing:8px; } QCheckBox::indicator { width:24px; height:24px; }")
        app = QApplication.instance()
        app.setStyleSheet(app.styleSheet() + f' QWidget {{ font-family:"{selected_font()}"; font-size:{self.settings.font_px}px; }}')
        self.input.setStyleSheet(f"font-size:{max(22,self.settings.font_px)}px;")

    def expand(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def collapse(self):
        self.compact.show()
        self.hide()

    def toggle_speech(self, enabled):
        self.speaker.set_enabled(enabled)
        self.settings = replace(self.settings, speech=enabled)
        try:
            save(self.settings)
        except OSError:
            self.voice_note.setText("Voice setting applies now but could not be saved.")

    def open_settings(self):
        dialog = SetupDialog(self.settings,self)
        if dialog.exec():
            self.settings = dialog.settings
            self.apply_style()

    def set_running(self, running):
        for control in (self.start,self.example,self.input,self.settings_button):
            control.setEnabled(not running)
        self.stop.setEnabled(running)
        self.compact.stop_button.setEnabled(running)
        self.compact.open_button.setEnabled(not running)

    def start_task(self):
        if self.worker and self.worker.isRunning():
            return
        text = self.input.toPlainText()
        from .planning import parse_task
        try:
            parse_task(text,self.settings.engine)
        except UserError as exc:
            self.update_status("error",str(exc))
            return
        self.set_running(True)
        self.worker = TaskWorker(self.settings,text)
        self.worker.status.connect(self.update_status)
        self.worker.finished.connect(self.task_finished)
        self.collapse()
        self.worker.start()

    def stop_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop_event.set()
            self.update_status("inactive","Stopping the task...")
            self.speaker.set_enabled(self.voice.isChecked())  # purge older speech

    def task_finished(self):
        self.set_running(False)
        # Do not raise over the final browser results or steal focus.

    def update_status(self, state, message):
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color:{COLORS[state]}; font-weight:bold;")
        self.compact.status(state,message)
        if state in {"success","error"} or message == "Opening your browser":
            self.speaker.say(message)

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.stop_task()
            event.ignore()
            return
        self.speaker.close()
        self.compact.hide()
        event.accept()
        QApplication.instance().quit()
