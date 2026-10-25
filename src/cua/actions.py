"""Action validation and a deliberately restricted desktop executor."""
import math
from .config import UserError
from .models import Cancelled
from .planning import Action, enforce_policy


def validate_action(action: Action):
    if action.kind not in {"click", "double_click", "type_text", "press_key", "scroll", "hotkey", "wait", "capture_screen", "finish_task", "request_user_help"}:
        raise UserError("This action is not supported.")
    if not isinstance(action.text, str) or len(action.text) > 2000 or any(ord(c) < 32 for c in action.text):
        raise UserError("The proposed text is not safe to enter.")
    if type(action.keys) is not tuple or len(action.keys) > 3 or any(k not in {"ctrl", "l", "enter", "esc", "tab"} for k in action.keys):
        raise UserError("This keyboard shortcut is not allowed.")
    if action.kind in {"hotkey", "press_key"} and not action.keys:
        raise UserError("The model did not specify a key.")
    for value in (action.x, action.y):
        if value is not None and (type(value) not in (float,int) or not math.isfinite(value) or not 0 <= value <= 1):
            raise UserError("The target is outside the browser window.")
    if action.kind in {"click", "double_click"} and (action.x is None or action.y is None):
        raise UserError("The model did not locate a target.")
    if type(action.amount) is not int or abs(action.amount) > 5:
        raise UserError("The scroll distance is too large.")
    if type(action.seconds) not in (int,float) or not math.isfinite(action.seconds) or not 0 <= action.seconds <= 3:
        raise UserError("The wait time is too long.")


class Executor:
    def __init__(self, browser):
        self.browser = browser

    def execute(self, action, stage, task, stop):
        validate_action(action)
        enforce_policy(action, stage, task)
        if stop.is_set():
            raise Cancelled()
        if action.kind == "request_user_help":
            raise UserError("I need your help. Check that the browser is visible and no sign-in or consent dialog is covering it.")
        if action.kind in {"wait", "capture_screen"}:
            if stop.wait(action.seconds if action.kind == "wait" else .1):
                raise Cancelled()
            return
        # Even if another caller constructs an action directly, the search policy
        # is checked here as well as in the planner. Generic clicks stay disabled.
        self.browser.guard()
        if action.kind == "hotkey":
            self.browser.focus_address(stop)
        elif action.kind == "type_text":
            self.browser.set_address(action.text, stop)
        elif action.kind == "press_key":
            self.browser.submit(task.url, stop)
