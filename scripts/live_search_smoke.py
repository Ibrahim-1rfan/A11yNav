"""Explicit live model/desktop search check. Brings the browser forward and sends browser images locally."""
from pathlib import Path
import sys
import threading
import time
import argparse
import ast
import re
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cua.browser import WindowsBrowser, enable_dpi_awareness
from cua.config import load, UserError
from cua.controller import Controller
from cua.models import LocalModel
from cua.perception import ScreenCapture

if __name__ == "__main__":
    import pythoncom
    parser = argparse.ArgumentParser()
    parser.add_argument("--one-step", action="store_true", help="Inspect one reply without executing it")
    parser.add_argument("--submit-step", action="store_true", help="Inspect the Enter step instead of the focus step")
    args = parser.parse_args()
    pythoncom.CoInitialize()
    enable_dpi_awareness()
    settings = load()
    started = time.monotonic()
    def status(state, message):
        print(f"{time.monotonic()-started:.1f}s {state}: {message}", flush=True)
    class DiagnosticModel(LocalModel):
        def _request(self, path, body=None):
            data = super()._request(path, body)
            if body is not None:
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                # Metadata only: never record browser image, query or answer text.
                status("diagnostic", f"Reply characters: {len(content or '')}; generation ended: {choice.get('finish_reason')}")
                expression = (content or '').rsplit('Action:', 1)[-1].strip()
                functions = re.findall(r'\b([a-z_]{1,30})\s*\(', expression)
                status("diagnostic", f"Action function names: {functions}; code fence present: {'```' in expression}")
                try:
                    node = ast.parse(expression, mode='eval').body
                    if isinstance(node, ast.Call):
                        status("diagnostic", f"Positional arguments: {len(node.args)}; keyword names: {[k.arg for k in node.keywords]}")
                except SyntaxError:
                    status("diagnostic", "Action expression has invalid syntax")
            return data
    try:
        if args.one_step:
            browser = WindowsBrowser(settings.browser)
            browser.open("https://www.google.com/", threading.Event())
            frame = ScreenCapture().capture(browser.bounds(), settings.max_image_edge)
            instruction = "Current approved step 3/4: Submit the address using hotkey enter. Mouse clicks and scrolling are forbidden. If the screen does not support this step, call_user." if args.submit_step else "Current approved step 1/4: Focus the browser address bar using the keyboard shortcut ctrl l. Do not type yet. Mouse clicks and scrolling are forbidden, including clicks on the address bar or search field. If the screen does not support this step, call_user."
            action = DiagnosticModel(settings).propose(frame, instruction,
                threading.Event(), settings.request_timeout)
            status("diagnostic", f"Parsed action kind: {action.kind}. No action executed.")
            raise SystemExit(0)
        result = Controller(settings, DiagnosticModel(settings), ScreenCapture(),
                            WindowsBrowser(settings.browser), status).run(
                                "Search for accessible computer interfaces", threading.Event())
        print(f"Result: {result}", flush=True)
        raise SystemExit(0 if result == "success" else 1)
    except UserError as exc:
        status("error", str(exc))
        raise SystemExit(1) from None
    finally:
        pythoncom.CoUninitialize()
