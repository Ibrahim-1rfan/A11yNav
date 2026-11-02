"""Short answer card: one-line title, up to three numbered steps, key chips, Replay / Slower / More options."""
import html
import re
from urllib.parse import urlsplit
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QVariantAnimation, Qt, Signal
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

VISIBLE_STEPS = 3
KEYS = r"Ctrl|Alt|Shift|Esc|Escape|Tab|Enter|Delete|Home|End|Page Down|Page Up|Print Screen|F\d{1,2}|Plus \(\+\)|Minus \(-\)"


def rich_step(text, colors):
    """Escape the step and render keyboard keys as chips, e.g. "Ctrl and Plus (+)" -> [Ctrl] and [+]."""
    def chip(key):
        key = {"Plus (+)": "+", "Minus (-)": "−"}.get(key, key)
        return (f'<span style="background:{colors["kbd_bg"]}; color:{colors["kbd_text"]}; font-family:Consolas,monospace;'
                f' font-weight:600;">&nbsp;{html.escape(key)}&nbsp;</span>')
    parts, last = [], 0
    pattern = re.compile(rf"\b({KEYS})(?![\w])|(?<=\band )([A-Z0-9])\b|(?<=\bCtrl and )([A-Z0-9])\b")
    for match in pattern.finditer(text):
        parts.append(html.escape(text[last:match.start()]))
        parts.append(chip(match.group(0)))
        last = match.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts)


class AnswerCard(QFrame):
    replay = Signal()
    slower = Signal(bool)
    more = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.colors = {}
        self.answer, self.active, self.expanded = None, -1, False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        self.title = QLabel()
        self.title.setObjectName("cardTitle")
        layout.addWidget(self.title)
        self.steps_box = QVBoxLayout()
        self.steps_box.setSpacing(4)
        layout.addLayout(self.steps_box)
        self.note = QLabel()
        self.note.setObjectName("note")
        self.note.setWordWrap(True)
        self.note.setOpenExternalLinks(True)
        self.note.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.note)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.replay_button, self.slower_button, self.more_button = QPushButton("Replay"), QPushButton("Slower"), QPushButton("More options")
        self.replay_button.setAccessibleName("Replay the answer from step 1")
        self.slower_button.setCheckable(True)
        self.slower_button.setAccessibleName("Read more slowly")
        self.more_button.setAccessibleName("Show more steps")
        self.replay_button.clicked.connect(self.replay)
        self.slower_button.toggled.connect(self.slower)
        self.more_button.clicked.connect(self.toggle_more)
        for button in (self.replay_button, self.slower_button, self.more_button):
            button.setObjectName("cardButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        self.step_labels = []
        self.fade = QGraphicsOpacityEffect(self)
        self.fade.setOpacity(1.0)
        self.setGraphicsEffect(self.fade)

    def show_answer(self, answer, colors, slower=False):
        self.answer, self.colors, self.active, self.expanded = answer, colors, -1, False
        self.slower_button.blockSignals(True)
        self.slower_button.setChecked(slower)
        self.slower_button.blockSignals(False)
        title = re.sub(r"\s*\(.*?\)", "", answer.title).strip() if answer.grounded else "No guide for that yet"
        self.title.setText(title)
        self.title.setToolTip(answer.title)
        self.render()
        self.enter()

    @property
    def visible_steps(self):
        steps = self.answer.steps if self.answer else ()
        return steps if self.expanded else steps[:VISIBLE_STEPS]

    def toggle_more(self):
        self.expanded = not self.expanded
        self.render()
        self.more.emit(self.expanded)

    def render(self):
        for label in self.step_labels:
            label.deleteLater()
        self.step_labels = []
        for i, step in enumerate(self.visible_steps):
            label = QLabel()
            label.setObjectName("step")
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setText(f'<b style="color:{self.colors["accent_text"]};">{i + 1}.</b>&nbsp; {rich_step(step, self.colors)}')
            label.setAccessibleName(f"Step {i + 1}: {step}")
            self.steps_box.addWidget(label)
            self.step_labels.append(label)
        extra = len(self.answer.steps) - VISIBLE_STEPS if self.answer else 0
        self.more_button.setVisible(extra > 0)
        self.more_button.setText("Fewer options" if self.expanded else "More options")
        self.more_button.setAccessibleName("Show fewer steps" if self.expanded else f"Show {extra} more steps")
        has_steps = bool(self.answer and self.answer.steps)
        self.replay_button.setVisible(has_steps)
        self.slower_button.setVisible(has_steps)
        notes = []
        if self.answer and not self.answer.grounded:
            notes.append(html.escape(self.answer.note))
        elif self.answer and self.expanded:
            if self.answer.note:
                notes.append(html.escape(self.answer.note))
            for source in self.answer.sources:
                if source.startswith("https://"):
                    notes.append(f'Source: <a style="color:{self.colors["accent_text"]};" href="{html.escape(source)}">'
                                 f'{html.escape(urlsplit(source).hostname or source)}</a>')
        self.note.setText("<br>".join(notes))
        self.note.setVisible(bool(notes))
        self.set_active(self.active)

    def set_active(self, index):
        """Highlight the step being read; -1 clears it."""
        self.active = index
        for i, label in enumerate(self.step_labels):
            on = i == index
            label.setProperty("active", "true" if on else "false")
            label.style().unpolish(label)
            label.style().polish(label)

    def enter(self):
        """200 ms fade with an 8 px upward slide."""
        if getattr(self, "reduced", False):
            self.fade.setOpacity(1.0)
            return
        self.fade_anim = QPropertyAnimation(self.fade, b"opacity", self)
        self.fade_anim.setDuration(200)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()
        # Slide the contents up 8 px by trading bottom margin for top margin; the card's size never changes.
        self.slide = QVariantAnimation(self)
        self.slide.setDuration(200)
        self.slide.setStartValue(8)
        self.slide.setEndValue(0)
        self.slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.slide.valueChanged.connect(lambda v: self.layout().setContentsMargins(16, 16 + int(v), 16, 16 - int(v)))
        self.slide.start()
