"""Guided steps inside a web page (the LMS): read a step, point at its link or button, wait for the person's click.

Pages load after each click, so a step's control is looked up again until it appears. A step whose spec is "any"
(choose an assignment, type an answer) has nothing fixed to point at, so any click outside Klicky moves on.
Trailing "tip" steps (what you'll see once there) are read after the last click instead of waited on.
The accessibility tree is asked first. If it can't find the control (or it stays out of sight), a vision model
looks at a screenshot for it, at most twice per step; it may answer with the collapsed menu that hides it, which is
pointed at first and whose click is not the step. Klicky never clicks or types in the page itself.
"""
import time
from PySide6.QtCore import QObject, QTimer
from . import page
from .tts import spoken
from .walkthrough import REMIND_AFTER_S, short_turn

CHECK_MS = 1000     # look for the step's control again while it hasn't appeared (the page may still be loading)
GIVE_UP_TRIES = 12  # after this many lookups without it, any click counts so the person is never stuck
LOOK_AFTER_TRIES = 2  # tree lookups (about 2 s of page loading) before asking the vision model
LOOK_LIMIT = 2        # vision lookups per step: each one is a screenshot and a model call
PAGE_SETTLE_MS = 1200  # after the click, let the next page load before reading the next step
CLICK_MENU_MS = 500    # after opening a collapsed menu, let it unfold before looking inside


class PageWalkthrough(QObject):
    def __init__(self, dock, steps, points, hwnd, chosen="", start=0, lead="", finder=None, worker_factory=None, seer=None):
        super().__init__()
        self.dock, self.steps, self.hwnd, self.chosen = dock, list(steps), hwnd, chosen
        self.points = list(points) + ["any"] * (len(self.steps) - len(points))
        self.walked = next((i for i, spec in enumerate(self.points) if spec == "tip"), len(self.steps))  # steps to click
        self.first, self.lead = start, lead
        self.finder = finder or page.find
        self.worker_factory = worker_factory or page.PageWorker
        self.seer = seer  # (hwnd, spec, chosen, step) -> vision.Seen or None; None means no vision fallback
        self.looks, self.revealing, self.by_eye = 0, False, False
        self.index, self.active, self.advancing = start, True, False
        self.worker = None
        self.tries, self.told_scroll, self.reminded, self.waiting_since = 0, False, False, 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(CHECK_MS)
        self.timer.timeout.connect(self.check)

    def start(self):
        self.say_step(self.first, lead=self.lead)

    def say_step(self, index, lead=""):
        self.timer.stop()
        self.advancing, self.index, self.tries, self.told_scroll = False, index, 0, False
        self.looks, self.revealing, self.by_eye = 0, False, False
        self.dock.highlighter.clear()
        self.dock.card.show_from(index)
        self.dock.reposition()
        if self.dock.state != "speaking":
            self.dock.machine.fire("next")
        lines = ([lead] if lead else []) + [spoken(self.steps[index])]
        last = len(lines) - 1
        self.dock.speak(lines, on_line_start=lambda line: self.show_step(index) if line == last else None,
                        on_end=lambda: self.await_step(index))

    def show_step(self, index):
        if not self.active or index != self.index:
            return
        self.dock.card.set_active(0)
        self.point(index)

    def point(self, index):
        spec = self.points[index]
        if spec == "any":
            self.dock.highlighter.clear()
            return
        if self.worker and self.worker.isRunning():
            return
        self.tries += 1
        self.worker = self.worker_factory(self.finder, self.hwnd, spec, self.chosen)
        self.worker.result.connect(lambda value, index=index: self.located(index, value))
        self.worker.start()

    def look(self, index):
        """Ask the vision model where the step's control is on screen."""
        if not self.seer or self.looks >= LOOK_LIMIT or (self.worker and self.worker.isRunning()):
            return
        self.looks += 1
        self.worker = self.worker_factory(self.seer, self.hwnd, self.points[index], self.chosen, self.steps[index])
        self.worker.result.connect(lambda seen, index=index: self.seen(index, seen))
        self.worker.start()

    def seen(self, index, seen):
        if not self.active or index != self.index or seen is None:
            return
        self.dock.highlighter.show_page(seen.rect)
        self.revealing, self.by_eye = seen.reveals, True
        if seen.reveals and self.dock.state == "waiting":
            self.dock.set_caption("It's inside this menu. Open it first.")

    def located(self, index, value):
        if not self.active or index != self.index:
            return
        rect, hidden = value if value else (None, False)
        if rect and not hidden:
            self.revealing = self.by_eye = False
            self.dock.highlighter.show_page(rect)
            return
        if self.revealing or self.by_eye:
            return  # a late empty lookup must not undo what the vision model found (or the menu it found)
        self.dock.highlighter.clear()
        if rect and hidden and not self.told_scroll and self.dock.state == "waiting":
            self.told_scroll = True
            self.dock.set_caption(f"Scroll {'up' if hidden == 'above' else 'down'} a little to find it.")
        # Not in the tree, or still out of sight after a while (a narrow page folds menus away): look at the screen.
        if self.tries >= (LOOK_AFTER_TRIES if not rect else 2 * LOOK_AFTER_TRIES):
            self.look(index)

    def await_step(self, index):
        if not self.active or index != self.index:
            return
        self.dock.machine.fire("wait")
        self.dock.set_caption(short_turn(self.steps[index]))
        if self.dock.pointed_rect is None:
            self.point(index)
        self.waiting_since, self.reminded = time.monotonic(), False
        self.timer.start()

    def check(self):
        if not self.active or self.dock.state != "waiting":
            return
        if not self.reminded and time.monotonic() - self.waiting_since > REMIND_AFTER_S:
            self.reminded = True
            self.dock.speak([f"When you're ready: {spoken(self.steps[self.index])}"])
        if self.points[self.index] != "any" and (self.dock.pointed_rect is None or self.revealing) and self.tries < GIVE_UP_TRIES:
            self.point(self.index)

    def clicked(self, point):
        if not (self.active and self.dock.state == "waiting") or self.advancing:
            return
        rect = self.dock.pointed_rect
        if self.points[self.index] != "any":
            if rect is None and self.tries < GIVE_UP_TRIES:
                return  # still looking for the control; a stray click isn't the step
            if rect is not None and not rect.adjusted(-6, -6, 6, 6).contains(point):
                return
            if self.revealing and rect is not None:
                # They opened the menu: now find the control inside it (tree first, then a fresh look).
                self.revealing, self.by_eye, self.tries, self.looks = False, False, 0, 0
                self.dock.highlighter.clear()
                QTimer.singleShot(CLICK_MENU_MS, lambda index=self.index: self.active and self.index == index and self.point(index))
                return
        if self.index >= self.walked - 1:
            self.finish()
            return
        self.advancing = True
        self.timer.stop()
        self.dock.highlighter.clear()
        nxt = self.index + 1
        QTimer.singleShot(PAGE_SETTLE_MS, lambda: self.active and self.say_step(nxt))

    def finish(self):
        self.timer.stop()
        self.active = False
        self.dock.highlighter.clear()
        if self.dock.state != "speaking":
            self.dock.machine.fire("next")
        tips = self.steps[self.walked:]
        if tips:
            self.dock.card.show_from(self.walked)
            self.dock.reposition()
        self.dock.speak(["That's it, well done."] + [spoken(tip) for tip in tips],
                        on_line_start=lambda line: self.dock.card.set_active(line - 1) if line else None,
                        on_end=self.dock.on_read_end)

    def stop(self):
        self.active = False
        self.timer.stop()
