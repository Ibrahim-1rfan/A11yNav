"""Observe, propose, validate, act, verify with hard task/attempt budgets."""
import logging
import time
from .actions import Executor, validate_action
from .config import UserError
from .models import Cancelled, ModelTransportError
from .planning import parse_task, enforce_policy
from .verification import verify_step

LOG = logging.getLogger("klicky")


class Controller:
    def __init__(self, settings, model, capture, browser, emit):
        self.settings, self.model, self.capture, self.browser, self.emit = settings, model, capture, browser, emit

    def run(self, text, stop):
        deadline = time.monotonic()+self.settings.task_timeout
        attempts, stage, errors = 0, 0, 0
        retry_note = ""
        def check():
            if stop.is_set():
                raise Cancelled()
            if time.monotonic() >= deadline:
                raise UserError(f"The {self.settings.task_timeout:g}-second task limit was reached at step {stage+1}/4. Increase the whole-task limit in Settings or reduce image size. Check the browser before trying again.")
        try:
            self.emit("processing", "Understanding your request")
            task = parse_task(text, self.settings.engine)
            self.emit("processing", "Checking the local model")
            self.model.health(stop)
            check()
            self.emit("action", "Opening your browser")
            self.browser.open(task.home, stop)
            if stop.wait(self.settings.settle_seconds):
                raise Cancelled()
            executor = Executor(self.browser)
            while attempts < self.settings.max_actions:
                check()
                self.browser.guard()
                self.emit("processing", "Looking at the browser")
                frame = self.capture.capture(self.browser.bounds(), self.settings.max_image_edge)
                steps = [
                    "Focus the browser address bar using the keyboard shortcut ctrl l. Do not type yet. Do not click the address bar or search field.",
                    f"Enter exactly this HTTPS search address with type: {task.url!r}. This encodes the user's query.",
                    "Submit the address using hotkey enter.",
                    f"Verify the screenshot shows actual search result links for {task.query!r}. Only return finished if the matching query and result links are visible. A blank/loading/error page, homepage, consent dialog, CAPTCHA or sign-in is NOT success. If loading, wait; if blocked, call_user.",
                ]
                instruction = f"Current approved step {stage+1}/4: {steps[stage]} Follow only the current step. Mouse clicks and scrolling are forbidden, including clicks on the address bar or search field. If the screen does not support this step, call_user. {retry_note}"
                self.emit("processing", f"Step {stage+1}/4: waiting for the local model (up to {min(self.settings.request_timeout, max(0, deadline-time.monotonic())):.0f} seconds)")
                attempts += 1  # Invalid replies and waits consume the same finite budget.
                try:
                    action = self.model.propose(frame, instruction, stop, deadline-time.monotonic())
                    validate_action(action)
                    enforce_policy(action, stage, task)
                except ModelTransportError:
                    raise
                except UserError as exc:
                    check()
                    errors += 1
                    if errors > self.settings.max_retries:
                        raise
                    retry_note = f"The previous reply was rejected: {exc} Choose only the action requested for this step."
                    self.emit("processing", f"{exc} Retrying step {stage+1}/4 ({errors}/{self.settings.max_retries}).")
                    continue
                check()
                if action.kind == "finish_task":
                    if not verify_step(3, self.browser, task):
                        raise UserError("I could not confirm the search address. Please check the browser results yourself.")
                    check()
                    self.emit("success", "The search results are now displayed.")
                    return "success"
                self.emit("action", "Searching for your requested topic" if stage in (1,2) else "Performing the next step")
                executor.execute(action, stage, task, stop)
                check()
                if stop.wait(self.settings.settle_seconds):
                    raise Cancelled()
                self.emit("processing", "Checking whether it worked")
                # Fresh observation after every executed action, before continuing.
                self.capture.capture(self.browser.bounds(), self.settings.max_image_edge)
                if action.kind in {"wait", "capture_screen"}:
                    continue
                # After Enter, allow a bounded URL-load delay; never re-submit it.
                for retry in range(self.settings.max_retries+1):
                    check()
                    if verify_step(stage, self.browser, task):
                        break
                    if retry == self.settings.max_retries:
                        raise UserError("I could not verify the last step. Please check the browser and try again.")
                    if stop.wait(self.settings.settle_seconds):
                        raise Cancelled()
                stage += 1
                errors = 0
                retry_note = ""
            raise UserError("I reached the action limit without confirming results. Please check the browser.")
        except Cancelled:
            self.emit("inactive", "Task stopped")
            return "stopped"
        except UserError as exc:
            self.emit("error", str(exc))
            return "error"
        except Exception as exc:
            # Never log screenshots, query, model answer, exception text or URLs.
            LOG.error("Task failed: %s", type(exc).__name__)
            self.emit("error", "I could not continue safely. Check that the browser is visible and try again.")
            return "error"
