"""Short answer card: one-line title and up to three numbered steps with key chips. No buttons."""
import html
import re
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QVariantAnimation, Qt
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout

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
    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.colors = {}
        self.answer, self.active = None, -1
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
        layout.addWidget(self.note)
        self.step_labels = []
        self.fade = QGraphicsOpacityEffect(self)
        self.fade.setOpacity(1.0)
        self.setGraphicsEffect(self.fade)

    def show_answer(self, answer, colors):
        self.answer, self.colors, self.active = answer, colors, -1
        title = re.sub(r"\s*\(.*?\)", "", answer.title).strip() if answer.grounded else "No guide for that yet"
        self.title.setText(title)
        self.title.setToolTip(answer.title)
        self.render()
        self.enter()

    @property
    def visible_steps(self):
        return self.answer.steps[:VISIBLE_STEPS] if self.answer else ()

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
        note = self.answer.note if self.answer and not self.answer.grounded else ""
        self.note.setText(note)
        self.note.setVisible(bool(note))
        self.set_active(self.active)

    def set_active(self, index):
        """Highlight the step being read; -1 clears it."""
        self.active = index
        for i, label in enumerate(self.step_labels):
            label.setProperty("active", "true" if i == index else "false")
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
