"""Guided steps inside a web page (the LMS): read a step, point at its link or button, wait for the person's click.

Pages load after each click, so a step's control is looked up again until it appears. A step whose spec is "any"
(type an answer) has nothing fixed to point at, so any click outside Klicky moves on. Trailing "tip" steps (what
you'll see once there) are read after the last click instead of waited on.
The accessibility tree is asked first. If it can't find the control (or it stays out of sight), a vision model
looks at a screenshot for it, at most twice per step; it may answer with the collapsed menu that hides it, which is
pointed at first and whose click is not the step. Klicky never clicks or types in the page itself.

An "assignment" step reads the course's Assignments list: it says which ones aren't submitted yet and when they're
due, points at the first, and listens for another name. Once one is opened, its page is read: a submitted one ends
the walkthrough ("you don't have to worry about this one"); otherwise its due date and a short summary of its
instructions are read before the next step.

When the person asked Klicky to go there itself ("show me the syllabus of Computer Security"), course and menu-link
steps are done by Klicky: the companion flies to the link and Klicky opens it through UI Automation (never a button
such as Proceed or Submit, and never with the mouse). The first step that needs the person is guided as usual.
"""
import logging
import time
from datetime import datetime
from types import SimpleNamespace
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
NAMED_AT_MOST = 3      # unsubmitted assignments read out by name; the rest are counted
AUTO_WAIT_MS = 300     # doing it for the person: look for the link again this often while the page loads
AUTO_TRIES = 12        # about 4 s; then the person is asked to click it instead
PRESS_MS = 700         # the companion rests on the link a moment, so the person sees what is opened
LOG = logging.getLogger("klicky.walk")  # step numbers and counts only, never what the page says


def page_reader(settings):
    """The real page readers and summarizer (tests pass fakes with the same three names)."""
    from .summary import summarize
    return SimpleNamespace(assignments=page.assignments, opened=page.opened_assignment,
                           summarize=lambda title, instructions: summarize(title, instructions, settings))


def still_open(rows, now=None):
    """Assignments not submitted whose due date hasn't passed (or isn't known), in the list's order."""
    now = now or datetime.now()
    return [row for row in rows if not row.submitted and (page.due_time(row.due) or now) >= now]


def ask_line(waiting):
    if not waiting:
        return "Everything that's still open is submitted. Click an assignment to check it, or tell me its name."
    if len(waiting) == 1:
        row = waiting[0]
        return (f"Which assignment? {row.title} isn't submitted yet. It's due {page.spoken_time(row.due)}. "
                "I'm pointing at it: click it, or tell me another one.")
    named = "; ".join(f"{row.title}, due {page.spoken_time(row.due)}" for row in waiting[:NAMED_AT_MOST])
    more = f", and {len(waiting) - NAMED_AT_MOST} more" if len(waiting) > NAMED_AT_MOST else ""
    return f"Which assignment? {len(waiting)} aren't submitted yet: {named}{more}. Click one, or tell me its name."


def status_lines(found, title, summary, now=None):
    """What to say about an opened assignment that isn't submitted: its due date, then what it asks for."""
    due = page.due_time(found.due)
    if due and due < (now or datetime.now()):
        when = f" Its due date, {page.spoken_time(found.due)}, has passed, so the LMS may not accept it."
    else:
        when = f" It's due {page.spoken_time(found.due)}." if found.due else ""
    return [f"{title} isn't submitted yet.{when}"] + ([f"Here's what it asks: {summary}"] if summary else [])


class PageWalkthrough(QObject):
    def __init__(self, dock, steps, points, hwnd, chosen="", start=0, lead="", finder=None, worker_factory=None, seer=None,
                 reader=None, question="", auto=False, presser=None):
        super().__init__()
        self.dock, self.steps, self.hwnd, self.chosen = dock, list(steps), hwnd, chosen
        self.points = list(points) + ["any"] * (len(self.steps) - len(points))
        self.walked = next((i for i, spec in enumerate(self.points) if spec == "tip"), len(self.steps))  # steps to click
        self.first, self.lead = start, lead
        self.finder = finder or page.find
        self.worker_factory = worker_factory or page.PageWorker
        self.seer = seer  # (hwnd, spec, chosen, step) -> vision.Seen or None; None means no vision fallback
        self.reader = reader  # assignments(hwnd), opened(hwnd), summarize(title, text); None: "assignment" acts as "any"
        self.question = question  # the person's question: it may name the assignment already
        self.auto, self.presser, self.pressed_last = auto, presser or page.press, False  # Klicky opens links itself
        self.looks, self.revealing, self.by_eye = 0, False, False
        self.index, self.active, self.advancing = start, True, False
        self.worker, self.tasks = None, []
        self.rows, self.picked, self.asking, self.wants_answer, self.misses = None, "", False, False, 0
        self.tries, self.told_scroll, self.reminded, self.waiting_since = 0, False, False, 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(CHECK_MS)
        self.timer.timeout.connect(self.check)

    def start(self):
        LOG.info("walk: %d steps %s, starting at %d", len(self.steps), self.points, self.first)
        self.say_step(self.first, lead=self.lead)

    def spec(self, index):
        """What step index points at: for the "assignment" step, the chosen assignment's own link."""
        spec = self.points[index]
        if spec == "assignment":
            return f"link: {self.picked}" if self.picked else "any"
        return spec

    def choosing(self, index=None):
        """At the "assignment" step with the list read: any click on the page may be the person's choice."""
        index = self.index if index is None else index
        return self.points[index] == "assignment" and bool(self.rows)

    def run(self, fn, *args, done):
        """A page read or model call off the UI thread; earlier ones are kept until they finish."""
        self.tasks = [task for task in self.tasks if task.isRunning()]
        task = self.worker_factory(fn, *args)
        task.result.connect(done)
        self.tasks.append(task)
        task.start()

    def say_step(self, index, lead=""):
        self.timer.stop()
        self.advancing, self.index, self.tries, self.told_scroll = False, index, 0, False
        self.looks, self.revealing, self.by_eye = 0, False, False
        self.dock.highlighter.clear()
        self.dock.card.show_from(index, 1)  # only the step being done; the next appears once it's done
        self.dock.reposition()
        LOG.info("step %d (%s), dock %s", index, self.points[index], self.dock.state)
        if self.dock.state != "speaking":
            self.dock.machine.fire("next")
        lines = list(lead) if isinstance(lead, (list, tuple)) else [lead] if lead else []
        if self.points[index] == "assignment" and self.rows is None and self.reader:
            self.dock.set_caption("Looking at your assignments...")
            self.run(self.reader.assignments, self.hwnd, done=lambda rows, index=index: self.on_list(index, rows or [], lines))
            return
        if self.auto_step(index):
            self.speak_step(index, lines + [self.opening(index)], on_end=lambda: self.press_when_found(index))
            return
        self.speak_step(index, lines + [spoken(self.steps[index])])

    def speak_step(self, index, lines, on_end=None):
        last = len(lines) - 1
        self.dock.speak(lines, on_line_start=lambda line: self.show_step(index) if line == last else None,
                        on_end=on_end or (lambda: self.await_step(index)))

    # ---- doing it for the person: open the course and its menu links ---------------------------------------
    def auto_step(self, index):
        return self.auto and self.points[index].partition(":")[0].strip() in page.PRESSABLE

    def opening(self, index):
        kind, _, name = self.points[index].partition(":")
        return f"Opening {page.short_name(self.chosen) if kind.strip() == 'course' else name.split('|')[0].strip()}."

    def press_when_found(self, index, tries=0):
        """Once the link is boxed on screen, open it; while the page still loads, look again."""
        if not self.active or index != self.index:
            return
        if self.dock.pointed_rect is None or self.by_eye:
            if tries >= AUTO_TRIES or self.by_eye:  # only seen in a screenshot: it can't be pressed, so the person clicks
                self.hand_over(index)
                return
            if tries % 3 == 2:
                self.point(index)
            QTimer.singleShot(AUTO_WAIT_MS, lambda: self.press_when_found(index, tries + 1))
            return
        QTimer.singleShot(PRESS_MS, lambda: self.active and self.index == index and self.press_now(index))

    def press_now(self, index):
        companion = getattr(getattr(self.dock, "owner", None), "companion", None)
        if companion is not None:
            companion.press()  # the companion squishes as if it clicked
        self.run(self.presser, self.hwnd, self.points[index], self.chosen, done=lambda ok, index=index: self.on_pressed(index, ok))

    def on_pressed(self, index, ok):
        if not self.active or index != self.index:
            return
        LOG.info("opened step %d myself: %s", index, bool(ok))
        if not ok:
            self.hand_over(index)
            return
        self.pressed_last = True
        self.advance()

    def hand_over(self, index):
        """Klicky couldn't open it: the person clicks this one, and the rest are guided."""
        self.auto = False
        self.speak_step(index, ["I couldn't open it myself. Please click it."])

    def on_list(self, index, rows, lines):
        if not self.active or index != self.index:
            return
        self.rows = rows
        LOG.info("assignments list: %d rows, %d not submitted", len(rows), sum(not row.submitted for row in rows))
        if not rows:  # not the list: maybe an assignment is open already, so read that
            self.run(self.reader.opened, self.hwnd, done=lambda found, index=index: self.on_open_already(index, found, lines))
            return
        waiting = still_open(rows)
        named = page.pick(self.question, [row.title for row in rows], numbers=False)  # "submit my week 8 reading"
        if named:
            self.picked = named
            line = f"Okay, {named}. Click it to open it."
        else:
            self.picked, self.asking = (waiting[0].title if waiting else ""), True
            line = ask_line(waiting)
        if waiting:
            self.dock.card.show_note("Not submitted yet: " + "; ".join(f"{row.title} (due {row.due})" for row in waiting))
        self.speak_step(index, lines + [line])

    def on_open_already(self, index, found, lines):
        if not self.active or index != self.index:
            return
        LOG.info("open assignment instead of the list: %s", "none" if found is None else "submitted" if found.submitted else "open")
        if found is None:  # neither the list nor an assignment: the step as written, and any click moves on
            self.speak_step(index, lines + [spoken(self.steps[index])])
            return
        self.on_opened(index, found)

    def show_step(self, index):
        if not self.active or index != self.index:
            return
        self.dock.card.set_active(0)
        self.point(index)

    def point(self, index):
        spec = self.spec(index)
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
        self.worker = self.worker_factory(self.seer, self.hwnd, self.spec(index), self.chosen, self.steps[index])
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
        if not self.active or index != self.index or self.advancing:
            return
        self.dock.machine.fire("wait")
        self.dock.set_caption("Click the assignment you want, or say its name." if self.asking and self.choosing(index)
                              else short_turn(self.steps[index]))
        if self.dock.pointed_rect is None:
            self.point(index)
        self.waiting_since, self.reminded = time.monotonic(), False
        self.timer.start()
        if self.asking and self.choosing(index):
            self.wants_answer = self.dock.listen_for_walk()

    def answered(self, text):
        """The person said which assignment (Klicky is thinking): point at it, or ask once more."""
        self.wants_answer = False
        if not (self.active and self.choosing()):
            return
        titles = [row.title for row in self.rows]
        chosen = page.pick(text, titles)
        self.dock.machine.fire("answer_read")
        self.dock.highlighter.clear()
        if chosen:
            self.picked, self.asking = chosen, False
            self.speak_step(self.index, [f"Okay, {chosen}. Click it to open it."])
            return
        self.misses += 1
        if self.misses >= 2:
            self.asking = False
            self.speak_step(self.index, ["I didn't catch that. Click the assignment you want."])
            return
        example = (still_open(self.rows) or self.rows)[0].title
        self.speak_step(self.index, [f"Sorry, which assignment? Say its name, for example {example}."])

    def check(self):
        if not self.active or self.dock.state != "waiting":
            return
        if not self.reminded and time.monotonic() - self.waiting_since > REMIND_AFTER_S:
            self.reminded = True
            self.dock.speak([f"When you're ready: {spoken(self.steps[self.index])}"])
        if self.spec(self.index) != "any" and (self.dock.pointed_rect is None or self.revealing) and self.tries < GIVE_UP_TRIES:
            self.point(self.index)

    def clicked(self, point):
        LOG.info("click at step %d (%s), dock %s, pointed %s", self.index, self.spec(self.index).split(":")[0],
                 self.dock.state, self.dock.pointed_rect is not None)
        if self.active and self.choosing() and not self.advancing and self.dock.state in ("waiting", "listening", "speaking"):
            self.chose()  # any assignment may be the one: its page says which it was
            return
        if not (self.active and self.dock.state == "waiting") or self.advancing:
            return
        rect = self.dock.pointed_rect
        if self.spec(self.index) != "any":
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
        self.pressed_last = False
        self.advance()

    def advance(self):
        """The step is done: on to the next one once its page has loaded, or the end."""
        if self.index >= self.walked - 1:
            self.finish()
            return
        self.advancing = True
        self.timer.stop()
        self.dock.highlighter.clear()
        nxt = self.index + 1
        QTimer.singleShot(PAGE_SETTLE_MS, lambda: self.active and self.say_step(nxt))

    # ---- the opened assignment: submitted, or what it asks for ------------------------------------------------
    def chose(self):
        self.advancing, self.asking = True, False
        self.timer.stop()
        if self.wants_answer:
            self.wants_answer = False
            self.dock.stop_listener()
        if self.dock.state == "speaking":
            self.dock.stop_speech()
        self.dock.highlighter.clear()
        index = self.index
        QTimer.singleShot(PAGE_SETTLE_MS, lambda: self.active and self.index == index and self.read_opened(index))

    def read_opened(self, index):
        self.dock.set_caption("Reading the assignment...")
        self.run(self.reader.opened, self.hwnd, done=lambda found, index=index: self.on_opened(index, found))

    def on_opened(self, index, found):
        if not self.active or index != self.index:
            return
        LOG.info("opened assignment: %s", "none" if found is None else "submitted" if found.submitted else
                 f"open, {len(found.instructions)} characters of instructions")
        if found is None:  # not an assignment page (a click elsewhere): keep waiting for the choice
            self.advancing = False
            self.dock.set_caption("Click the assignment you want to open.")
            self.timer.start()
            return
        title = found.title or self.picked or "This assignment"
        if found.submitted:
            when = f", on {page.spoken_time(found.submitted_on)}" if found.submitted_on else ""
            self.dock.card.show_note(f"{title}: submitted" + (f" {found.submitted_on}" if found.submitted_on else ""))
            self.end_with([f"{title} is already submitted{when}. You don't have to worry about this one."])
            return
        self.dock.set_caption("Reading the instructions...")
        self.run(self.reader.summarize, title, found.instructions,
                 done=lambda summary, index=index: self.on_summary(index, found, title, summary or ""))

    def on_summary(self, index, found, title, summary):
        if not self.active or index != self.index:
            return
        lines = status_lines(found, title, summary)
        self.dock.card.show_note(" ".join(lines))
        if index + 1 >= self.walked:
            self.end_with(lines)
            return
        self.say_step(index + 1, lead=lines)

    def end_with(self, lines):
        """The walkthrough is over early, with these words instead of "well done"."""
        self.timer.stop()
        self.active = False
        self.dock.highlighter.clear()
        if self.dock.state != "speaking":
            self.dock.machine.fire("next")
        self.dock.set_caption(lines[0])
        self.dock.speak(lines, on_end=self.dock.on_read_end)

    def finish(self):
        self.timer.stop()
        self.active = False
        self.dock.highlighter.clear()
        if self.dock.state != "speaking":
            self.dock.machine.fire("next")
        tips = self.steps[self.walked:]
        if tips:
            self.dock.card.show_from(self.walked, len(tips))
            self.dock.reposition()
        done = "Here it is." if self.pressed_last else "That's it, well done."
        self.dock.speak([done] + [spoken(tip) for tip in tips],
                        on_line_start=lambda line: self.dock.card.set_active(line - 1) if line else None,
                        on_end=self.dock.on_read_end)

    def stop(self):
        self.active = False
        self.timer.stop()
