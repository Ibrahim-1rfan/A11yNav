"""Multi-step guidance: read one step, point at its control, wait for the person to do it, then go on.

Progress is judged by what the browser shows, not by guessing: a step is done when the next step's control
appears (for example the menu opened, by click or by Alt+F), and the last step is done when its control is
clicked. If a menu closes before the person finishes, Klicky steps back and asks them to open it again.
"""
import time
from PySide6.QtCore import QObject, QTimer
from .highlighter import ControlLocator, target_for
from .tts import intro, spoken

CHECK_MS = 400        # how often the browser is checked while waiting for the person
REMIND_AFTER_S = 20   # one gentle spoken reminder if nothing happens
MISSING_CHECKS = 2    # a menu counts as closed after this many checks without its control
CLICK_SETTLE_MS = 350 # after a click on the pointed control, let the menu open before pointing into it


def actionable_steps(steps):
    """How many leading steps each point at a control. Two or more make a walkthrough."""
    count = 0
    for step in steps:
        if not target_for(step):
            break
        count += 1
    return count


def short_turn(step, limit=80):
    sentence = step.split(". ")[0].rstrip(".")
    if len(sentence) > limit:
        sentence = sentence[:limit].rsplit(" ", 1)[0] + "…"
    return f"Your turn: {sentence[0].lower() + sentence[1:]}."


class Walkthrough(QObject):
    def __init__(self, dock, steps, actionable, hwnd, probe_factory=None):
        super().__init__()
        self.dock, self.steps, self.actionable, self.hwnd = dock, list(steps), actionable, hwnd
        self.probe_factory = probe_factory or ControlLocator
        self.index = 0
        self.active = True
        self.probe = None
        self.phase = 0
        self.missing = 0
        self.seen = False
        self.advancing = False  # a click was accepted; ignore more clicks until the next step is read
        self.waiting_since = 0.0
        self.reminded = False
        self.timer = QTimer(self)
        self.timer.setInterval(CHECK_MS)
        self.timer.timeout.connect(self.check)

    # ---- speaking ------------------------------------------------------------------------------------------
    def start(self):
        self.say_step(0, lead=intro(self.dock.answer))

    def say_step(self, index, lead=""):
        self.timer.stop()
        self.advancing = False
        self.index = index
        if self.dock.state != "speaking":
            self.dock.machine.fire("next")
        lines = ([lead] if lead else []) + [spoken(self.steps[index])]
        last = len(lines) - 1
        self.dock.speak(lines, on_line_start=lambda line: self.show_step(index) if line == last else None,
                        on_end=lambda: self.await_step(index))

    def show_step(self, index):
        self.dock.card.set_active(index)
        self.dock.highlighter.point(self.steps[index], self.hwnd)

    def await_step(self, index):
        if not self.active:
            return
        self.show_step(index)  # in case the line callback raced the end
        self.dock.machine.fire("wait")
        self.dock.set_caption(short_turn(self.steps[index]))
        self.waiting_since, self.reminded, self.missing, self.phase, self.seen = time.monotonic(), False, 0, 0, False
        self.timer.start()

    def finish(self):
        """The last control was used: say so, then read any remaining tips."""
        self.timer.stop()
        self.active = False
        self.dock.highlighter.clear()
        if self.dock.state != "speaking":
            self.dock.machine.fire("next")
        rest = self.steps[self.actionable:]
        lines = ["That's it, well done."] + [spoken(step) for step in rest]
        self.dock.speak(lines, on_line_start=lambda line: self.dock.card.set_active(self.actionable + line - 1) if line else None,
                        on_end=self.dock.on_read_end)

    def step_back(self):
        """The menu closed before the person finished: ask for it again."""
        self.timer.stop()
        previous = max(0, self.index - 1)
        self.say_step(previous, lead="The menu closed. Let's open it again.")

    # ---- watching the browser ------------------------------------------------------------------------------
    def check(self):
        if not self.active or self.dock.state != "waiting" or (self.probe and self.probe.isRunning()):
            return
        if not self.reminded and time.monotonic() - self.waiting_since > REMIND_AFTER_S:
            self.reminded = True
            self.dock.speak([f"When you're ready: {spoken(self.steps[self.index])}"])
        nxt = self.index + 1
        # Alternate: is the next step's control showing yet? Is this step's (menu) control still there?
        if nxt < self.actionable and (self.phase == 0 or self.index == 0):
            self.run_probe(target_for(self.steps[nxt]), lambda rect: rect and self.say_step(nxt))
        elif self.index > 0:
            self.run_probe(target_for(self.steps[self.index]), self.own_control)
        self.phase ^= 1

    def own_control(self, rect):
        # Only a control that was seen and then vanished means the menu closed. If Klicky cannot recognise the
        # menu's controls at all, it keeps waiting for the person's click instead of wrongly stepping back.
        if rect:
            self.seen, self.missing = True, 0
            return
        self.missing += 1
        if self.seen and self.missing >= MISSING_CHECKS:
            self.step_back()

    def run_probe(self, target, then):
        self.probe = self.probe_factory(self.hwnd, target)
        self.probe.found.connect(lambda _target, rect: self.active and self.dock.state == "waiting" and then(rect))
        self.probe.start()

    def clicked(self, point):
        """The person clicked the control Klicky is pointing at: that step is done, so say the next one."""
        rect = self.dock.pointed_rect
        if not (self.active and self.dock.state == "waiting") or self.advancing:
            return
        # Normally the click must land on the pointed control. If Klicky could not find that control, any click
        # outside Klicky counts: the person did the step themselves, and waiting forever would be a dead end.
        if rect is not None and not rect.adjusted(-6, -6, 6, 6).contains(point):
            return
        if self.index >= self.actionable - 1:
            self.finish()
        else:
            # Give the browser a moment to open the menu before pointing inside it.
            self.advancing = True
            nxt = self.index + 1
            QTimer.singleShot(CLICK_SETTLE_MS, lambda: self.active and self.say_step(nxt))
            self.timer.stop()

    def stop(self):
        self.active = False
        self.timer.stop()
