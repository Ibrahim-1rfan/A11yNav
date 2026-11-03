"""Accessible Qt interface, persistent stop widget, guided answers and first-run model settings."""
from dataclasses import replace
import threading
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEvent
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QCursor, QFont, QFontDatabase, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QTextEdit, QTextBrowser, QCheckBox, QDialog, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QDialogButtonBox, QMessageBox, QScrollArea, QSystemTrayIcon, QMenu)
from .config import Settings, UserError, save
from .models import LocalModel, LocalText
from .browser import WindowsBrowser, foreground_app
from .controller import Controller
from .hotkey import GlobalHotkey
from .popup import AnswerWorker, answer_html
from .dock import Dock
from .perception import ScreenCapture
from .speech import Speaker
from . import profiles

# Tried in order only when the default shortcut is owned by another app. Avoids browser and screen-reader keys.
FALLBACK_HOTKEYS = ["Ctrl+Alt+F9"]
EXAMPLES = ["Search for accessible computer interfaces", "How do I make text bigger in Edge?", "How can Chrome read this page aloud?"]


def selected_font(profile=None):
    available = QFontDatabase.families()
    names = (profile or profiles.get("default")).fonts
    found = next((name for name in names if name in available), None)
    if found:
        return found
    if names == profiles.MONO:
        return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()


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
            if self.settings.text_model or self.settings.embed_model:
                LocalText(self.settings).health(threading.Event())
            self.result.emit(True, "Server and models found. Image capability is checked during your task.")
        except UserError as exc:
            self.result.emit(False, str(exc))


class SetupDialog(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.setWindowTitle("Klicky settings")
        self.resize(720, 680)
        self.settings = settings
        self.check_worker = None
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        intro = QLabel("1. Choose the access profile that suits you. You can change it at any time.\n2. Load a vision model and its projector in LM Studio, and start the local server in its Developer tab.\n3. Copy the exact model identifier below. Use ui_tars for UI-TARS, or json for Qwen2.5-VL.\n4. Optional: add a text model to write answers in your profile's style, and an embedding model for smarter guide matching.\nThe search needs at least four model replies. Allow enough time for the whole task.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.profile = QComboBox()
        for key, profile in profiles.PROFILES.items():
            self.profile.addItem(profile.label, key)
        self.profile.setCurrentIndex(self.profile.findData(settings.profile))
        self.profile_note = QLabel(profiles.get(settings.profile).description)
        self.profile_note.setWordWrap(True)
        self.endpoint, self.model = QLineEdit(settings.endpoint), QLineEdit(settings.model)
        self.text_model, self.embed_model = QLineEdit(settings.text_model), QLineEdit(settings.embed_model)
        self.hotkey = QLineEdit(settings.hotkey)
        self.listen = QCheckBox("Start listening when Klicky opens")
        self.listen.setChecked(settings.voice)
        self.read_aloud = QCheckBox("Read answers aloud")
        self.read_aloud.setChecked(settings.read_aloud)
        self.barge = QCheckBox("Stop reading when I start talking")
        self.barge.setChecked(settings.barge_in)
        self.reader_quiet = QCheckBox("Let my screen reader read answers instead, when one is running")
        self.reader_quiet.setChecked(settings.screen_reader_quiet)
        self.show_companion = QCheckBox("Show Klicky companion next to the pointer")
        self.show_companion.setChecked(settings.companion)
        self.companion_speed = QComboBox()
        for label, key in (("Gentle", "gentle"), ("Normal", "normal"), ("Snappy", "snappy")):
            self.companion_speed.addItem(label, key)
        self.companion_speed.setCurrentIndex(max(0, self.companion_speed.findData(settings.companion_speed)))
        self.click_ripple = QCheckBox("Show a ripple when I click")
        self.click_ripple.setChecked(settings.click_ripple)
        self.allow_actions = QCheckBox("Let Klicky do simple browser tasks when I ask (new tab, refresh, zoom...)")
        self.allow_actions.setChecked(settings.actions)
        from .tts import list_voices
        self.tts_voice = QComboBox()
        self.tts_voice.addItem("Windows default", "")
        for name in list_voices():
            self.tts_voice.addItem(name, name)
        self.tts_voice.setCurrentIndex(max(0, self.tts_voice.findData(settings.tts_voice)))
        from .neural_tts import VOICES
        self.voice_engine = QComboBox()
        self.voice_engine.addItem("Natural (online: the text read is sent to Microsoft)", "natural")
        self.voice_engine.addItem("Windows (offline)", "windows")
        self.voice_engine.setCurrentIndex(max(0, self.voice_engine.findData(settings.voice_engine)))
        self.neural_voice = QComboBox()
        for name, label in VOICES.items():
            self.neural_voice.addItem(label, name)
        if self.neural_voice.findData(settings.neural_voice) < 0:
            self.neural_voice.addItem(settings.neural_voice, settings.neural_voice)
        self.neural_voice.setCurrentIndex(max(0, self.neural_voice.findData(settings.neural_voice)))
        self.speech_rate = QComboBox()
        for label, rate in (("Slower", .8), ("Normal", 1.0), ("Faster", 1.2)):
            self.speech_rate.addItem(label, rate)
        self.speech_rate.setCurrentIndex(min(range(3), key=lambda i: abs(self.speech_rate.itemData(i) - settings.speech_rate)))
        self.hotkey.setPlaceholderText("For example Win+Shift+K. Leave empty to turn off.")
        self.text_model.setPlaceholderText("Optional, for example qwen2.5-3b-instruct")
        self.embed_model.setPlaceholderText("Optional, for example text-embedding-nomic-embed-text-v1.5")
        self.adapter, self.browser, self.engine, self.rag_app = QComboBox(), QComboBox(), QComboBox(), QComboBox()
        for combo, values, current in [(self.adapter, ["ui_tars", "json"], settings.adapter), (self.browser, ["default", "edge", "chrome", "firefox"], settings.browser), (self.engine, ["bing", "google", "duckduckgo"], settings.engine), (self.rag_app, ["auto", "edge", "chrome", "firefox"], settings.rag_app)]:
            combo.addItems(values)
            combo.setCurrentText(current)
        self.vision = QComboBox()
        for value, text in [("auto", "Auto: the first one with a key set, else the local model"),
                            ("openrouter", "UI-TARS on OpenRouter (screenshot sent to OpenRouter)"),
                            ("huggingface", "UI-TARS on Hugging Face (screenshot sent to Hugging Face)"),
                            ("claude", "Claude (screenshot sent to Anthropic)"),
                            ("local", "Local model (screenshot stays on this PC)"), ("off", "Off: page names only")]:
            self.vision.addItem(text, value)
        self.vision.setCurrentIndex(max(0, self.vision.findData(settings.vision)))
        self.vision.setToolTip("When a guided step's button can't be found by its name, look at a screenshot of the browser to find it. "
                               "Keys come from environment variables: OPENROUTER_API_KEY, HF_TOKEN or ANTHROPIC_API_KEY.")
        self.vision_model = QLineEdit(settings.vision_model)
        self.size, self.limit, self.timeout = QSpinBox(), QSpinBox(), QSpinBox()
        self.task_timeout, self.image_edge, self.tokens = QSpinBox(), QSpinBox(), QSpinBox()
        for control, lo, hi, value in [(self.size,16,40,settings.font_px),(self.limit,3,30,settings.max_actions),(self.timeout,1,120,int(settings.request_timeout)),(self.task_timeout,10,600,int(settings.task_timeout)),(self.image_edge,640,1920,settings.max_image_edge),(self.tokens,128,2048,settings.max_tokens)]:
            control.setRange(lo,hi)
            control.setValue(value)
        self.profile.currentIndexChanged.connect(self.profile_changed)
        for label, control in [("Access profile",self.profile),("Shortcut to open Klicky from any app",self.hotkey),("Voice questions",self.listen),("Answers",self.read_aloud),("Voice type",self.voice_engine),("Natural voice",self.neural_voice),("Windows voice",self.tts_voice),("Reading speed",self.speech_rate),("Barge-in",self.barge),("Screen reader",self.reader_quiet),("Companion",self.show_companion),("Companion follow speed",self.companion_speed),("Click ripple",self.click_ripple),("Browser tasks",self.allow_actions),("Local server",self.endpoint),("Model identifier",self.model),("Model adapter",self.adapter),("Answer model (optional)",self.text_model),("Embedding model (optional)",self.embed_model),("Guides for browser",self.rag_app),("Finding buttons by looking",self.vision),("Claude vision model",self.vision_model),("Browser preference",self.browser),("Search engine",self.engine),("Text size",self.size),("Action limit",self.limit),("Model timeout in seconds",self.timeout),("Whole-task limit in seconds",self.task_timeout),("Image longest edge in pixels",self.image_edge),("Maximum reply tokens",self.tokens)]:
            control.setAccessibleName(label)
            form.addRow(label,control)
            if control is self.profile:
                form.addRow("", self.profile_note)
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

    def profile_changed(self):
        profile = profiles.get(self.profile.currentData())
        self.profile_note.setText(profile.description)
        self.size.setValue(profile.font_px)

    def values(self):
        key = self.profile.currentData()
        base = self.settings if key == self.settings.profile else profiles.apply_to(self.settings, key)
        return replace(base, endpoint=self.endpoint.text().strip(), model=self.model.text().strip(), adapter=self.adapter.currentText(), browser=self.browser.currentText(), engine=self.engine.currentText(), font_px=self.size.value(), max_actions=self.limit.value(), request_timeout=self.timeout.value(), task_timeout=self.task_timeout.value(), max_image_edge=self.image_edge.value(), max_tokens=self.tokens.value(),
                       text_model=self.text_model.text().strip(), embed_model=self.embed_model.text().strip(), rag_app=self.rag_app.currentText(),
                       vision=self.vision.currentData(), vision_model=self.vision_model.text().strip(),
                       hotkey=self.hotkey.text().strip(), voice=self.listen.isChecked(),
                       read_aloud=self.read_aloud.isChecked(), barge_in=self.barge.isChecked(),
                       screen_reader_quiet=self.reader_quiet.isChecked(), tts_voice=self.tts_voice.currentData(),
                       voice_engine=self.voice_engine.currentData(), neural_voice=self.neural_voice.currentData(),
                       speech_rate=self.speech_rate.currentData(), companion=self.show_companion.isChecked(),
                       companion_speed=self.companion_speed.currentData(), click_ripple=self.click_ripple.isChecked(),
                       actions=self.allow_actions.isChecked()).validate()

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
    ask = Signal()
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Klicky controls")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.profile = profiles.get("default")
        layout = QVBoxLayout(self)
        self.badge = QLabel(profiles.state_label(self.profile, "inactive"))
        self.badge.setAccessibleName("Agent state")
        self.message = QLabel("Ready for your command")
        self.message.setWordWrap(True)
        layout.addWidget(self.badge)
        layout.addWidget(self.message)
        row = QHBoxLayout()
        self.ask_button, self.open_button, self.stop_button = QPushButton("Ask"), QPushButton("Open"), QPushButton("Stop")
        self.ask_button.setObjectName("primary")
        self.ask_button.setAccessibleName("Ask Klicky a question")
        self.open_button.setAccessibleName("Open the Klicky window")
        self.ask_button.clicked.connect(self.ask)
        self.open_button.clicked.connect(self.expand)
        self.stop_button.clicked.connect(self.stop)
        self.stop_button.setEnabled(False)
        row.addWidget(self.ask_button)
        row.addWidget(self.open_button)
        row.addWidget(self.stop_button)
        layout.addLayout(row)
        self.idle_message = "Ready"
        self.set_profile(self.profile, 18)

    def set_profile(self, profile, font_px):
        self.profile = profile
        width = max(340, font_px * 17)
        self.setFixedWidth(width)
        self.stop_button.setMinimumHeight(profile.button_px + (12 if profile.key == "motor" else 0))
        self.status("inactive", self.message.text())
        geometry = QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        self.move(geometry.right() - width - 20, geometry.bottom() - self.height() - 40)

    def closeEvent(self, event):
        # The always-available entry point remains until the main app is closed.
        event.ignore()
        self.expand.emit()

    def status(self, state, message):
        color = self.profile.states[state]
        self.badge.setText(profiles.state_label(self.profile, state))
        self.badge.setStyleSheet(f"border:{max(3, self.profile.focus_px)}px solid {color}; color:{color}; border-radius:14px; padding:8px;")
        self.message.setText(message)


class MainWindow(QWidget):
    speech_error = Signal(str)
    def __init__(self, settings: Settings, startup_error=""):
        super().__init__()
        self.settings = settings
        self.worker = None
        self.answer = None
        self.step = 0
        self.setWindowTitle("Klicky | Accessible browser assistant")
        self.resize(820, 760)
        self.compact = CompactWidget()
        self.compact.stop.connect(self.stop_task)
        self.compact.expand.connect(self.expand)
        self.speaker = Speaker(self.speech_error.emit)
        self.speech_error.connect(lambda msg: self.voice_note.setText(msg))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        self.layout_main = layout = QVBoxLayout(content)
        layout.setContentsMargins(28,24,28,24)
        self.title = QLabel("Klicky")
        layout.addWidget(self.title)
        subtitle = QLabel("A little help finding your way.")
        layout.addWidget(subtitle)
        prompt_label = QLabel("Search the web, or ask how to do something in your browser:")
        prompt_label.setWordWrap(True)
        layout.addWidget(prompt_label)
        self.input = QTextEdit()
        self.input.setAccessibleName("Search or question")
        self.input.setPlaceholderText("Search for accessible computer interfaces\nHow do I make text bigger in Edge?")
        self.input.setMinimumHeight(130)
        self.input.setTabChangesFocus(True)
        self.input.installEventFilter(self)
        prompt_label.setBuddy(self.input)
        layout.addWidget(self.input)
        # Stacked, never side by side: wide rows would scroll the Stop button out of view at large text sizes.
        examples = QVBoxLayout()
        examples.setContentsMargins(0, 0, 0, 0)
        self.examples = []
        for text in EXAMPLES:
            button = QPushButton(f"Try: {text}")
            button.setAccessibleName(f"Use example: {text}")
            button.clicked.connect(lambda _=False, t=text: self.input.setPlainText(t))
            examples.addWidget(button)
            self.examples.append(button)
        self.example = self.examples[0]
        examples_box = QWidget()
        examples_box.setLayout(examples)
        layout.addWidget(examples_box)
        row = QHBoxLayout()
        self.start, self.stop = QPushButton("Go"), QPushButton("Stop")
        self.start.setObjectName("primary")
        self.start.setAccessibleName("Go: search or answer")
        self.start.setShortcut("Alt+S")
        self.stop.setShortcut("Alt+X")
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
        self.answer_view = QTextBrowser()
        self.answer_view.setAccessibleName("Answer")
        self.answer_view.setOpenExternalLinks(True)
        self.answer_view.setMinimumHeight(320)
        self.answer_view.hide()
        layout.addWidget(self.answer_view)
        steps = QHBoxLayout()
        self.back, self.next = QPushButton("Back"), QPushButton("Next step")
        self.back.setAccessibleName("Previous step")
        self.back.clicked.connect(lambda: self.show_step(self.step - 1))
        self.next.clicked.connect(lambda: self.show_step(self.step + 1))
        steps.addWidget(self.back)
        steps.addWidget(self.next)
        self.step_controls = QWidget()
        self.step_controls.setLayout(steps)
        self.step_controls.hide()
        layout.addWidget(self.step_controls)
        self.privacy = QLabel("When you search, Klicky opens a search tab and sends browser screenshots to your local model. Keep private information out of view. Search topics go to your chosen search engine. Questions stay on this computer.")
        self.privacy.setWordWrap(True)
        layout.addWidget(self.privacy)
        options = QGridLayout()
        self.voice = QCheckBox("Spoken feedback")
        self.voice.setChecked(settings.speech)
        self.voice.toggled.connect(self.toggle_speech)
        self.speaker.set_enabled(settings.speech)
        self.profile_box = QComboBox()
        self.profile_box.setAccessibleName("Access profile")
        for key, profile in profiles.PROFILES.items():
            self.profile_box.addItem(profile.label, key)
        self.profile_box.setCurrentIndex(self.profile_box.findData(settings.profile))
        self.profile_box.currentIndexChanged.connect(self.choose_profile)
        self.settings_button, self.compact_button = QPushButton("Settings"), QPushButton("Hide window")
        self.settings_button.clicked.connect(self.open_settings)
        self.compact_button.clicked.connect(self.collapse)
        options.addWidget(self.voice, 0, 0)
        options.addWidget(self.profile_box, 0, 1)
        options.addWidget(self.settings_button, 1, 0)
        options.addWidget(self.compact_button, 1, 1)
        layout.addLayout(options)
        self.voice_note = QLabel()
        self.voice_note.setWordWrap(True)
        layout.addWidget(self.voice_note)
        layout.addStretch()
        self.escape_shortcut = QShortcut(QKeySequence("Escape"),self)
        self.escape_shortcut.activated.connect(self.stop_task)
        self.dock = Dock(self)
        self.compact.ask.connect(lambda: self.open_orb(self.dock.context_app, self.dock.return_hwnd))
        # The companion trails the pointer over the browser and turns into the orb on the hotkey.
        from .companion import Companion
        self.companion = Companion(lambda: self.settings)
        self.dock.on_closed = self.companion.reappear
        self.companion.start()
        self.hotkey = GlobalHotkey()
        self.hotkey.triggered.connect(self.summon)
        self.hotkey_ok = self.register_hotkey()
        # Nothing stays on screen: Klicky waits in the tray, and the corner box appears only while a search runs.
        self.tray = self.make_tray()
        if settings.voice:
            from .voice import preload
            preload(settings.voice_model)
        self.apply_style()
        if startup_error:
            self.update_status("error", startup_error)

    def make_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#68e3b5"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 60, 60)
        font = QFont("Segoe UI")
        font.setPixelSize(38)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#0a202b"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "K")
        painter.end()
        tray = QSystemTrayIcon(QIcon(pixmap), self)
        menu = QMenu()
        self.tray_ask = menu.addAction("Ask Klicky", lambda: self.open_orb(self.dock.context_app, self.dock.return_hwnd))
        menu.addAction("Open Klicky window", self.expand)
        menu.addAction("Settings", lambda: (self.expand(), self.open_settings()))
        menu.addSeparator()
        menu.addAction("Quit Klicky", self.quit_app)
        tray.setContextMenu(menu)
        self.tray_menu = menu
        tray.activated.connect(lambda reason: self.tray_ask.trigger() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        tray.show()
        return tray

    def quit_app(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop_event.set()
            self.worker.wait(3000)
        self.hotkey.unregister()
        self.speaker.close()
        self.companion.stop()
        self.dock.close_dock()
        self.dock.tts.close()
        self.compact.hide()
        if self.tray:
            self.tray.hide()
        QApplication.instance().quit()

    def register_hotkey(self):
        """Register the chosen shortcut. Only the default falls back to alternatives when another app owns it."""
        self.active_hotkey = ""
        candidates = [self.settings.hotkey] + (FALLBACK_HOTKEYS if self.settings.hotkey == Settings.hotkey else [])
        for text in candidates:
            try:
                if text and self.hotkey.register(text):
                    self.active_hotkey = text
                    return True
            except (UserError, OSError, AttributeError):
                return False
        return False

    def summon(self):
        """Global shortcut: note which browser is in front, then float the Ask popup over it."""
        try:
            hwnd, app = foreground_app()
        except Exception:
            hwnd, app = None, None
        own = {int(self.winId()), int(self.compact.winId()), int(self.dock.winId())}
        if not hwnd or int(hwnd) in own:
            hwnd, app = self.dock.return_hwnd, self.dock.context_app
        self.open_orb(app, hwnd)

    def open_orb(self, app, hwnd):
        """The companion shrinks away and the orb pops in centred 18 px down-right of where it was.
        With the companion off or hidden, the orb opens at the pointer."""
        if not self.dock.isVisible() or self.dock.closing:
            if self.companion.is_showing():
                corner = self.companion.position()
                anchor = QPoint(corner.x() + 18, corner.y() + 18)
            else:
                anchor = QCursor.pos()
            self.companion.morph_out()
            self.dock.open_for(app, hwnd, anchor=anchor)
        else:
            self.dock.open_for(app, hwnd)

    def run_search(self, text):
        """A search typed into the popup runs through the normal guarded search agent."""
        self.input.setPlainText(text)
        self.start_task()

    @property
    def profile(self):
        return profiles.get(self.settings.profile)

    def apply_style(self):
        p, px = self.profile, self.settings.font_px
        c, family = p.colors, selected_font(p)
        font = QFont(family)
        font.setPixelSize(px)
        if p.letter_spacing:
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, p.letter_spacing)
        app = QApplication.instance()
        app.setFont(font)
        app.setStyleSheet(
            f'QWidget {{ background:{c["background"]}; color:{c["text"]}; font-family:"{family}"; font-size:{px}px; }}'
            f' QPushButton,QComboBox,QSpinBox,QLineEdit {{ padding:10px; border:1px solid {c["border"]}; border-radius:7px; min-height:{p.button_px-22}px; }}'
            f' QPushButton:focus,QTextEdit:focus,QTextBrowser:focus,QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QCheckBox:focus {{ border:{p.focus_px}px solid {c["focus"]}; }}'
            f' QPushButton:disabled {{ color:{c["muted"]}; background:{c["disabled"]}; }}'
            f' QPushButton#primary {{ background:{c["accent"]}; color:{c["on_accent"]}; font-weight:bold; }}'
            f' QPushButton#primary:disabled {{ color:{c["muted"]}; background:{c["disabled"]}; }}'
            f' QTextEdit,QTextBrowser {{ background:{c["surface"]}; border:2px solid {c["border"]}; border-radius:8px; padding:12px; }}'
            f' QCheckBox {{ spacing:8px; }} QCheckBox::indicator {{ width:{max(24, px)}px; height:{max(24, px)}px; }}'
            f' a {{ color:{c["accent"]}; }}')
        self.layout_main.setSpacing(p.spacing)
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(available.width() - 40, max(self.width(), 820, px * 28)), min(available.height() - 40, max(self.height(), 760)))
        self.title.setStyleSheet(f"font-size:{px + 14}px; font-weight:bold; color:{c['accent']};")
        self.privacy.setStyleSheet(f"color:{c['muted']};")
        self.input.setStyleSheet(f"font-size:{max(p.input_px, px + 4)}px;")
        shortcut = (f"Press {self.active_hotkey} in any app to ask Klicky. " if self.hotkey_ok and self.active_hotkey else
                    f"{self.settings.hotkey} is already used by another app; choose another shortcut in Settings. " if self.settings.hotkey else "")
        self.voice_note.setText(shortcut + "Keyboard: " + ("Enter starts, Shift and Enter adds a new line. " if p.enter_starts else "Alt+S starts. ") + "Alt+X or Escape stops while this window is focused.")
        self.compact.set_profile(p, px)
        self.compact.idle_message = f"Press {self.active_hotkey} in your browser to ask" if self.active_hotkey else "Ready"
        if not (self.worker and self.worker.isRunning()):
            self.compact.status("inactive", self.compact.idle_message)
        if self.tray:
            self.tray.setToolTip(f"Klicky: press {self.active_hotkey} to ask" if self.active_hotkey else "Klicky")
            self.tray_ask.setText(f"Ask Klicky ({self.active_hotkey})" if self.active_hotkey else "Ask Klicky")
        if self.dock.isVisible():
            self.dock.restyle()
        if not (self.worker and self.worker.isRunning()):
            self.update_status("inactive", self.status_label.text())
        if self.answer:
            self.render_answer()

    def choose_profile(self):
        key = self.profile_box.currentData()
        if key == self.settings.profile:
            return
        self.settings = profiles.apply_to(self.settings, key)
        self.voice.blockSignals(True)
        self.voice.setChecked(self.settings.speech)
        self.voice.blockSignals(False)
        self.speaker.set_enabled(self.settings.speech)
        try:
            save(self.settings)
        except OSError:
            self.voice_note.setText("Profile applies now but could not be saved.")
        self.apply_style()
        self.speaker.say(f"{self.profile.label} profile on.")

    def eventFilter(self, watched, event):
        if (watched is self.input and event.type() == QEvent.Type.KeyPress and self.profile.enter_starts
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.start_task()
            return True
        return super().eventFilter(watched, event)

    def expand(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def collapse(self):
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
            changed_hotkey = dialog.settings.hotkey != self.settings.hotkey
            self.settings = dialog.settings
            if changed_hotkey:
                self.hotkey_ok = self.register_hotkey()
            self.profile_box.blockSignals(True)
            self.profile_box.setCurrentIndex(self.profile_box.findData(self.settings.profile))
            self.profile_box.blockSignals(False)
            self.voice.setChecked(self.settings.speech)
            self.apply_style()

    def set_running(self, running):
        for control in (self.start,self.input,self.settings_button,self.profile_box,*self.examples):
            control.setEnabled(not running)
        self.stop.setEnabled(running)
        self.compact.stop_button.setEnabled(running)
        self.compact.open_button.setEnabled(not running)
        self.compact.ask_button.setEnabled(not running)

    def start_task(self):
        if self.worker and self.worker.isRunning():
            return
        text = self.input.toPlainText()
        from .planning import route, HelpQuestion
        try:
            routed = route(text,self.settings.engine)
        except UserError as exc:
            self.update_status("error",str(exc))
            return
        if isinstance(routed, HelpQuestion):
            self.ask(routed.question)
            return
        if self.profile.confirm_search and QMessageBox.question(
                self, "Start the search?", f"Klicky will open a new browser tab and search for:\n\n{routed.query}\n\nKeep your hands off the keyboard and mouse until it is done. Start now?") != QMessageBox.StandardButton.Yes:
            self.update_status("inactive", "Search not started.")
            return
        self.set_running(True)
        self.worker = TaskWorker(self.settings,text)
        self.worker.status.connect(self.update_status)
        self.worker.finished.connect(self.task_finished)
        self.collapse()
        self.compact.show()  # the Stop button stays reachable while Klicky controls the browser
        self.worker.start()

    def ask(self, question, factory=None):
        self.answer = None
        self.answer_view.hide()
        self.step_controls.hide()
        self.set_running(True)
        self.worker = AnswerWorker(self.settings, question, factory)
        self.worker.status.connect(self.update_status)
        self.worker.answered.connect(self.show_answer)
        self.worker.finished.connect(self.task_finished)
        self.worker.start()

    def show_answer(self, answer):
        self.answer, self.step = answer, 0
        self.render_answer()
        self.speaker.say(answer.spoken() if not (self.profile.one_step and answer.grounded) else f"{answer.title}. Step 1. {answer.steps[0]}")
        self.answer_view.setFocus()
        # Large text pushes the answer below the fold; bring it (and the step buttons) into view.
        QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(self.step_controls if self.step_controls.isVisible() else self.answer_view))

    def show_step(self, index):
        if not self.answer or not self.answer.steps:
            return
        self.step = max(0, min(index, len(self.answer.steps) - 1))
        self.render_answer()
        self.speaker.say(f"Step {self.step + 1}. {self.answer.steps[self.step]}")

    def render_answer(self):
        text, one_step = answer_html(self.answer, self.profile, self.step)
        self.answer_view.setHtml(text)
        self.answer_view.show()
        self.step_controls.setVisible(one_step)
        if one_step:
            self.back.setEnabled(self.step > 0)
            self.next.setEnabled(self.step < len(self.answer.steps) - 1)

    def stop_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop_event.set()
            self.update_status("inactive","Stopping...")
            self.speaker.set_enabled(self.voice.isChecked())  # purge older speech

    def task_finished(self):
        self.set_running(False)
        # Do not raise over the final browser results or steal focus; let the result be read, then clear the box.
        if isinstance(self.worker, TaskWorker):
            QTimer.singleShot(6000, lambda: self.compact.hide() if not (self.worker and self.worker.isRunning()) else None)

    def update_status(self, state, message):
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color:{self.profile.states[state]}; font-weight:bold;")
        self.compact.status(state,message)
        if (state in {"success","error"} or message == "Opening your browser") and not isinstance(self.worker, AnswerWorker):
            self.speaker.say(message)
        elif state == "error" and isinstance(self.worker, AnswerWorker):
            self.speaker.say(message)

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.stop_task()
            event.ignore()
            return
        if self.tray:
            # Closing the window keeps Klicky waiting for the shortcut; Quit lives in the tray menu.
            event.ignore()
            self.hide()
            return
        event.accept()
        self.quit_app()
